"""
run_crewai.py
Run CrewAI pipeline and save results to results/ca_result.json
Usage: PYTHONPATH=. python3 run_crewai.py ./data/sample_sas
"""

import os
import sys
import json
import time
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from crewai import Crew, Process
from crewai_pipeline.crew_agents import (
    make_dependency_planner_agent, make_rag_translator_agent,
    make_syntax_validator_agent, make_confidence_scorer_agent,
    make_report_generator_agent,
)
from crewai_pipeline.crew_tasks import (
    make_dependency_task, make_translation_task,
    make_validation_task, make_scoring_task, make_report_task,
)


def parse_crew_output(raw: str) -> list:
    """
    Parse CrewAI's markdown output into structured translation records.
    Extracts benchmark table rows if present.
    """
    records = []
    # Try to find markdown table rows: | filename | sas_loc | ...
    table_pattern = re.findall(
        r'\|\s*(\S+\.(?:sas|py))\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+%?)\s*\|\s*(\w+)\s*\|\s*[🟢🟡🔴⚪]?\s*(\w+)',
        raw
    )
    for row in table_pattern:
        fname, sas_loc, py_loc, score, t_sec, saved, pct, val, decision = row
        records.append({
            "filename":           fname,
            "cosine_score":       float(score),
            "sas_loc":            int(sas_loc),
            "py_loc":             int(py_loc),
            "translation_time":   float(t_sec),
            "validation_status":  val.lower(),
            "correction_attempts": 0,
            "routing_decision":   decision.upper(),
            "routing_reason":     "Parsed from CrewAI report",
            "python_code":        "",
            "tfl_flagged":        "REQUIRES_MANUAL_REVIEW" in raw,
        })

    # If table parsing failed, create summary records from routing mentions
    if not records:
        for decision, emoji in [("AUTO_APPROVED","🟢"), ("REVIEW_REQUIRED","🟡"), ("REJECTED","🔴")]:
            matches = re.findall(rf'{emoji}\s*{decision}.*?(\w+\.(?:sas|py))', raw)
            for fname in matches:
                records.append({
                    "filename":           fname,
                    "cosine_score":       0.0,
                    "sas_loc":            0,
                    "py_loc":             0,
                    "translation_time":   0,
                    "validation_status":  "reported",
                    "correction_attempts": 0,
                    "routing_decision":   decision,
                    "routing_reason":     "Parsed from CrewAI narrative",
                    "python_code":        "",
                    "tfl_flagged":        False,
                })

    return records


def run(sas_folder: str):
    os.makedirs("results", exist_ok=True)
    start = time.time()

    print("\n" + "="*60)
    print("🤖 ClinTranslate — CrewAI Pipeline")
    print(f"   Input: {sas_folder}")
    print("="*60)

    llm = "anthropic/claude-sonnet-4-6"

    planner_agent   = make_dependency_planner_agent(llm)
    translator_agent = make_rag_translator_agent(llm)
    validator_agent  = make_syntax_validator_agent(llm)
    scorer_agent     = make_confidence_scorer_agent(llm)
    reporter_agent   = make_report_generator_agent(llm)

    t1 = make_dependency_task(planner_agent, sas_folder)
    t2 = make_translation_task(translator_agent, sas_folder, [t1])
    t3 = make_validation_task(validator_agent, [t2])
    t4 = make_scoring_task(scorer_agent, [t3])
    t5 = make_report_task(reporter_agent, [t4])

    crew = Crew(
        agents=[planner_agent, translator_agent, validator_agent, scorer_agent, reporter_agent],
        tasks=[t1, t2, t3, t4, t5],
        process=Process.sequential,
        verbose=True,
    )

    print("\n🚀 Crew running...\n")
    crew_result = crew.kickoff()
    raw = str(crew_result)
    elapsed = round(time.time() - start, 1)

    # Save raw report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("reports", exist_ok=True)
    report_path = f"reports/crewai_report_{ts}.md"
    with open(report_path, "w") as f:
        f.write(f"# ClinTranslate — CrewAI Report\n")
        f.write(f"**Run:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Runtime:** {elapsed}s  \n\n---\n\n")
        f.write(raw)

    translations = parse_crew_output(raw)

    result = {
        "framework":      "CrewAI",
        "process":        "Sequential (role-based agents)",
        "run_timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sas_folder":     sas_folder,
        "elapsed_sec":    elapsed,
        "node_timings":   {},
        "file_count":     len(translations),
        "routing_summary": {t["filename"]: t["routing_decision"] for t in translations},
        "translations":   translations,
        "report_path":    report_path,
        "raw_output":     raw[:8000],  # cap for JSON size
        "stats": {
            "auto_approved":   sum(1 for t in translations if t["routing_decision"] == "AUTO_APPROVED"),
            "review_required": sum(1 for t in translations if t["routing_decision"] == "REVIEW_REQUIRED"),
            "rejected":        sum(1 for t in translations if t["routing_decision"] == "REJECTED"),
            "syntax_valid":    sum(1 for t in translations if t["validation_status"] in ("valid","reported")),
            "tfl_flagged":     sum(1 for t in translations if t["tfl_flagged"]),
            "avg_cosine":      round(sum(t["cosine_score"] for t in translations) / len(translations), 4) if translations else 0,
            "avg_time_sec":    round(sum(t["translation_time"] for t in translations) / len(translations), 1) if translations else 0,
            "total_sas_loc":   sum(t["sas_loc"] for t in translations),
            "total_py_loc":    sum(t["py_loc"] for t in translations),
        }
    }

    out = "results/ca_result.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ CrewAI complete — {elapsed}s | {len(translations)} files parsed")
    print(f"   Report: {report_path}")
    print(f"   JSON:   {out}")
    print(f"{'='*60}\n")
    return result


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "./data/sample_sas"
    if not os.path.isdir(folder):
        print(f"❌ Folder not found: {folder}")
        sys.exit(1)
    run(folder)
