"""
run_langgraph.py
Run LangGraph pipeline and save results to results/lg_result.json
Usage: python3 run_langgraph.py ./data/sample_sas
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from agents.dependency_planner import run_dependency_planner
from agents.rag_translator      import run_rag_translator
from agents.syntax_validator    import run_syntax_validator
from agents.confidence_scorer   import run_confidence_scorer
from agents.report_generator    import run_report_generator

def run(sas_folder: str):
    os.makedirs("results", exist_ok=True)
    start = time.time()

    print("\n" + "="*60)
    print("🔷 ClinTranslate — LangGraph Pipeline")
    print(f"   Input: {sas_folder}")
    print("="*60)

    state = {
        "sas_folder": sas_folder,
        "sas_files": [], "dependency_graph": {},
        "execution_order": [], "planner_notes": [],
        "translations": {}, "translator_notes": [],
        "validator_notes": [], "routing_summary": {},
        "scorer_notes": [], "report_paths": [],
    }

    agents = [
        ("plan",      "1️⃣  Dependency Planner", run_dependency_planner),
        ("translate", "2️⃣  RAG Translator",      run_rag_translator),
        ("validate",  "3️⃣  Syntax Validator",    run_syntax_validator),
        ("score",     "4️⃣  Confidence Scorer",   run_confidence_scorer),
        ("report",    "5️⃣  Report Generator",    run_report_generator),
    ]

    node_timings = {}
    notes_keys = {
        "plan": "planner_notes", "translate": "translator_notes",
        "validate": "validator_notes", "score": "scorer_notes",
        "report": "report_paths",
    }

    for node, label, fn in agents:
        if node != "plan" and not state.get("sas_files"):
            print(f"   ⚠️  No SAS files — stopping")
            break
        print(f"\n{label} — running...")
        t0 = time.time()
        state = fn(state)
        node_timings[label] = round(time.time() - t0, 2)
        notes = state.get(notes_keys[node], [])
        for n in (notes[:3] if notes and isinstance(notes[0], str) else []):
            print(f"   → {n}")
        print(f"   ✅ {node_timings[label]}s")

    elapsed = round(time.time() - start, 1)

    # Build serialisable summary
    translations = state.get("translations", {})
    summary = []
    for fname, data in translations.items():
        summary.append({
            "filename":          fname,
            "cosine_score":      data.get("cosine_score", 0),
            "sas_loc":           data.get("sas_loc", 0),
            "py_loc":            data.get("py_loc", 0),
            "translation_time":  data.get("translation_time_sec", 0),
            "validation_status": data.get("validation_status", "unknown"),
            "correction_attempts": data.get("correction_attempts", 0),
            "routing_decision":  data.get("routing_decision", "UNKNOWN"),
            "routing_reason":    data.get("routing_reason", ""),
            "python_code":       data.get("python_code", ""),
            "tfl_flagged":       "REQUIRES_MANUAL_REVIEW" in data.get("python_code", ""),
        })

    result = {
        "framework":     "LangGraph",
        "process":       "StateGraph (deterministic)",
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sas_folder":    sas_folder,
        "elapsed_sec":   elapsed,
        "node_timings":  node_timings,
        "file_count":    len(translations),
        "routing_summary": state.get("routing_summary", {}),
        "translations":  summary,
        "report_paths":  state.get("report_paths", []),
        "stats": {
            "auto_approved":    sum(1 for t in summary if t["routing_decision"] == "AUTO_APPROVED"),
            "review_required":  sum(1 for t in summary if t["routing_decision"] == "REVIEW_REQUIRED"),
            "rejected":         sum(1 for t in summary if t["routing_decision"] == "REJECTED"),
            "syntax_valid":     sum(1 for t in summary if t["validation_status"] == "valid"),
            "tfl_flagged":      sum(1 for t in summary if t["tfl_flagged"]),
            "avg_cosine":       round(sum(t["cosine_score"] for t in summary) / len(summary), 4) if summary else 0,
            "avg_time_sec":     round(sum(t["translation_time"] for t in summary) / len(summary), 1) if summary else 0,
            "total_sas_loc":    sum(t["sas_loc"] for t in summary),
            "total_py_loc":     sum(t["py_loc"] for t in summary),
        }
    }

    out = "results/lg_result.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ LangGraph complete — {elapsed}s | {len(translations)} files")
    print(f"   Saved: {out}")
    print(f"{'='*60}\n")
    return result

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "./data/sample_sas"
    if not os.path.isdir(folder):
        print(f"❌ Folder not found: {folder}")
        sys.exit(1)
    run(folder)
