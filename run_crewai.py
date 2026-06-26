"""
run_crewai.py
Run CrewAI pipeline and save results to results/ca_result.json
Usage: PYTHONPATH=. python3 run_crewai.py ./data/sample_sas
"""

import os
import sys
import json
import time
import glob
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


def parse_crew_output(raw: str, actual_files: list) -> list:
    """
    Parse CrewAI's markdown output into structured translation records.
    Falls back to actual file list if parsing yields no results.
    """
    records = []

    # Try to find markdown table rows
    table_pattern = re.findall(
        r'\|\s*(\S+\.sas)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|[^|]*\|[^|]*\|\s*(\w+)\s*\|[^|]*([A-Z_]+)',
        raw
    )
    for row in table_pattern:
        fname, sas_loc, py_loc, score, t_sec, val, decision = row
        decision = decision.strip()
        if decision not in ("AUTO_APPROVED", "REVIEW_REQUIRED", "REJECTED"):
            continue
        records.append({
            "filename":            fname,
            "cosine_score":        float(score),
            "sas_loc":             int(sas_loc),
            "py_loc":              int(py_loc),
            "translation_time":    float(t_sec),
            "validation_status":   val.lower(),
            "correction_attempts": 0,
            "routing_decision":    decision,
            "routing_reason":      f"Cosine {score} — parsed from CrewAI report",
            "python_code":         "",
            "tfl_flagged":         "REQUIRES_MANUAL_REVIEW" in raw and fname in raw,
        })

    # If table parsing found rows, return them
    if records:
        return records

    # Fallback: scan narrative for each actual file
    for filepath in actual_files:
        fname = os.path.basename(filepath)
        stem = fname.replace(".sas", "")

        # Determine routing from narrative mentions
        decision = "REVIEW_REQUIRED"  # default
        if re.search(rf'REJECTED.*{re.escape(stem)}|{re.escape(stem)}.*REJECTED', raw, re.I):
            decision = "REJECTED"
        elif re.search(rf'AUTO_APPROVED.*{re.escape(stem)}|{re.escape(stem)}.*AUTO_APPROVED', raw, re.I):
            decision = "AUTO_APPROVED"
        elif re.search(rf'REVIEW.*{re.escape(stem)}|{re.escape(stem)}.*REVIEW', raw, re.I):
            decision = "REVIEW_REQUIRED"

        # Check TFL flag
        tfl = bool(re.search(rf'TFL.*{re.escape(stem)}|{re.escape(stem)}.*TFL|PROC REPORT.*{re.escape(stem)}', raw, re.I))
        if tfl:
            decision = "REJECTED"

        # Try to extract cosine score near filename
        score_match = re.search(
            rf'{re.escape(stem)}[^\n]*?(0\.\d{{2,4}})', raw, re.I
        )
        score = float(score_match.group(1)) if score_match else 0.0

        records.append({
            "filename":            fname,
            "cosine_score":        score,
            "sas_loc":             0,
            "py_loc":              0,
            "translation_time":    0,
            "validation_status":   "reported",
            "correction_attempts": 0,
            "routing_decision":    decision,
            "routing_reason":      "Parsed from CrewAI narrative",
            "python_code":         "",
            "tfl_flagged":         tfl,
        })

    return records


def run(sas_folder: str):
    os.makedirs("results", exist_ok=True)
    start = time.time()

    # Get actual file list
    actual_files = sorted(glob.glob(os.path.join(sas_folder, "*.sas")))
    file_list = "\n".join([f"- {os.path.basename(f)}" for f in actual_files])

    print("\n" + "="*60)
    print("🤖 ClinTranslate — CrewAI Pipeline")
    print(f"   Input : {sas_folder}")
    print(f"   Files : {len(actual_files)} SAS programs")
    print("="*60)
    for f in actual_files:
        print(f"   → {os.path.basename(f)}")

    llm = "anthropic/claude-sonnet-4-6"

    planner_agent    = make_dependency_planner_agent(llm)
    translator_agent = make_rag_translator_agent(llm)
    validator_agent  = make_syntax_validator_agent(llm)
    scorer_agent     = make_confidence_scorer_agent(llm)
    reporter_agent   = make_report_generator_agent(llm)

    # Pass real file list into first two tasks
    t1 = make_dependency_task(planner_agent, sas_folder, file_list)
    t2 = make_translation_task(translator_agent, sas_folder, [t1], file_list)
    t3 = make_validation_task(validator_agent, [t2])
    t4 = make_scoring_task(scorer_agent, [t3])
    t5 = make_report_task(reporter_agent, [t4])

    crew = Crew(
        agents=[planner_agent, translator_agent, validator_agent,
                scorer_agent, reporter_agent],
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
        f.write(f"**Files:** {', '.join([os.path.basename(f) for f in actual_files])}  \n")
        f.write(f"**Runtime:** {elapsed}s  \n\n---\n\n")
        f.write(raw)

    translations = parse_crew_output(raw, actual_files)

    print(f"\n📋 Parsed {len(translations)} file results:")
    for t in translations:
        badge = {"AUTO_APPROVED":"🟢","REVIEW_REQUIRED":"🟡","REJECTED":"🔴"}.get(
            t["routing_decision"], "⚪")
        print(f"   {badge} {t['filename']} — {t['routing_decision']} | score={t['cosine_score']}")

    result = {
        "framework":       "CrewAI",
        "process":         "Sequential (role-based agents)",
        "run_timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sas_folder":      sas_folder,
        "elapsed_sec":     elapsed,
        "node_timings":    {},
        "file_count":      len(translations),
        "routing_summary": {t["filename"]: t["routing_decision"] for t in translations},
        "translations":    translations,
        "report_path":     report_path,
        "raw_output":      raw[:8000],
        "stats": {
            "auto_approved":   sum(1 for t in translations if t["routing_decision"] == "AUTO_APPROVED"),
            "review_required": sum(1 for t in translations if t["routing_decision"] == "REVIEW_REQUIRED"),
            "rejected":        sum(1 for t in translations if t["routing_decision"] == "REJECTED"),
            "syntax_valid":    sum(1 for t in translations if t["validation_status"] in ("valid","corrected","reported")),
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
    print(f"✅ CrewAI complete — {elapsed}s | {len(translations)} files")
    print(f"   🟢 Auto: {result['stats']['auto_approved']} | "
          f"🟡 Review: {result['stats']['review_required']} | "
          f"🔴 Rejected: {result['stats']['rejected']}")
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
