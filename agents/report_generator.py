"""
Agent 5: Report Generator
Produces:
  1. benchmarks/benchmark_results.csv  — per-program timing + scoring data
  2. reports/<filename>_validation.md  — per-program GxP-style validation report
  3. reports/pipeline_summary.md       — overall run summary
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import TypedDict, Dict, Any, List


BENCHMARK_DIR = "benchmarks"
REPORTS_DIR = "reports"
MANUAL_ESTIMATE_HOURS = 2.5  # industry baseline: hours per SAS program manually


class ReportState(TypedDict):
    translations: Dict[str, Dict[str, Any]]
    routing_summary: Dict[str, str]
    planner_notes: List[str]
    translator_notes: List[str]
    validator_notes: List[str]
    scorer_notes: List[str]
    execution_order: List[str]
    report_paths: List[str]


def _ensure_dirs():
    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


def _time_saved(translation_time_sec: float) -> float:
    """Estimate hours saved vs manual translation."""
    manual_hours = MANUAL_ESTIMATE_HOURS
    agent_hours = round(translation_time_sec / 3600, 4)
    return round(manual_hours - agent_hours, 4)


def write_benchmark_csv(translations: Dict[str, Dict[str, Any]]) -> str:
    """Write benchmark_results.csv with per-program metrics."""
    _ensure_dirs()
    path = os.path.join(BENCHMARK_DIR, "benchmark_results.csv")
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fieldnames = [
        "run_timestamp", "filename", "sas_loc", "py_loc",
        "cosine_score", "translation_time_sec", "estimated_manual_hours",
        "time_saved_hours", "pct_time_saved", "validation_status",
        "correction_attempts", "routing_decision",
    ]

    rows = []
    for filename, data in translations.items():
        t_sec = data.get("translation_time_sec", 0)
        saved = _time_saved(t_sec)
        pct = round((saved / MANUAL_ESTIMATE_HOURS) * 100, 1) if MANUAL_ESTIMATE_HOURS > 0 else 0

        rows.append({
            "run_timestamp": run_ts,
            "filename": filename,
            "sas_loc": data.get("sas_loc", 0),
            "py_loc": data.get("py_loc", 0),
            "cosine_score": data.get("cosine_score", 0.0),
            "translation_time_sec": t_sec,
            "estimated_manual_hours": MANUAL_ESTIMATE_HOURS,
            "time_saved_hours": saved,
            "pct_time_saved": pct,
            "validation_status": data.get("validation_status", "unknown"),
            "correction_attempts": data.get("correction_attempts", 0),
            "routing_decision": data.get("routing_decision", "UNKNOWN"),
        })

    file_exists = os.path.isfile(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    return path


def write_validation_report(filename: str, data: Dict[str, Any]) -> str:
    """Write a GxP-style validation markdown report for one program."""
    _ensure_dirs()
    stem = Path(filename).stem
    path = os.path.join(REPORTS_DIR, f"{stem}_validation.md")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    decision = data.get("routing_decision", "UNKNOWN")
    decision_badge = {
        "AUTO_APPROVED": "🟢 AUTO_APPROVED",
        "REVIEW_REQUIRED": "🟡 REVIEW_REQUIRED",
        "REJECTED": "🔴 REJECTED",
    }.get(decision, "⚪ UNKNOWN")

    t_sec = data.get("translation_time_sec", 0)
    saved = _time_saved(t_sec)
    pct = round((saved / MANUAL_ESTIMATE_HOURS) * 100, 1)

    python_code = data.get("python_code", "")
    tfl_flag = "⚠️ YES — PROC REPORT / ODS RTF detected. Manual TFL review required." \
        if "REQUIRES_MANUAL_REVIEW" in python_code else "✅ No TFL constructs detected"

    content = f"""# ClinTranslate v4 — Validation Report
**File:** {filename}  
**Generated:** {ts}  
**Tool:** ClinTranslate v4 Agentic Pipeline  
**Disclaimer:** Translated output requires IQ/OQ/PQ validation before use in any GxP/submission context.

---

## 1. Translation Decision
| Field | Value |
|---|---|
| Routing Decision | {decision_badge} |
| Routing Reason | {data.get("routing_reason", "N/A")} |
| Cosine Similarity Score | {data.get("cosine_score", 0.0)} |
| Syntax Validation | {data.get("validation_status", "unknown").upper()} |
| Self-Correction Attempts | {data.get("correction_attempts", 0)} |

---

## 2. Performance Metrics
| Metric | Value |
|---|---|
| SAS Lines of Code | {data.get("sas_loc", 0)} |
| Python Lines of Code | {data.get("py_loc", 0)} |
| Agent Translation Time | {t_sec}s ({round(t_sec/60, 1)} min) |
| Manual Estimate (baseline) | {MANUAL_ESTIMATE_HOURS} hrs |
| Estimated Time Saved | {saved} hrs ({pct}%) |

---

## 3. TFL / Output Detection
{tfl_flag}

---

## 4. Translated Python Output
```python
{python_code if python_code else "# No output — translation failed"}
```

---

## 5. GxP Review Checklist
- [ ] Reviewer verified variable names match source SAS
- [ ] Output dataset structure confirmed equivalent
- [ ] Logic verified against CDISC SDTM/ADaM specification
- [ ] Parallel run comparison completed (SAS vs Python outputs match)
- [ ] Reviewer signature / date: _______________

---
*ClinTranslate v4 | github.com/ravinsun/clintranslate | 21 CFR Part 11 Awareness*
"""

    with open(path, "w") as f:
        f.write(content)

    return path


def write_pipeline_summary(
    translations: Dict[str, Dict[str, Any]],
    execution_order: List[str],
    all_notes: List[str],
) -> str:
    """Write overall pipeline run summary."""
    _ensure_dirs()
    path = os.path.join(REPORTS_DIR, "pipeline_summary.md")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total = len(translations)
    approved = sum(1 for d in translations.values() if d.get("routing_decision") == "AUTO_APPROVED")
    review = sum(1 for d in translations.values() if d.get("routing_decision") == "REVIEW_REQUIRED")
    rejected = sum(1 for d in translations.values() if d.get("routing_decision") == "REJECTED")

    total_sas_loc = sum(d.get("sas_loc", 0) for d in translations.values())
    total_time_sec = sum(d.get("translation_time_sec", 0) for d in translations.values())
    total_saved = sum(_time_saved(d.get("translation_time_sec", 0)) for d in translations.values())
    avg_score = (
        sum(d.get("cosine_score", 0) for d in translations.values()) / total
        if total > 0 else 0
    )
    avg_pct_saved = round((total_saved / (MANUAL_ESTIMATE_HOURS * total)) * 100, 1) if total > 0 else 0

    rows = []
    for fname, data in translations.items():
        decision = data.get("routing_decision", "UNKNOWN")
        icon = {"AUTO_APPROVED": "🟢", "REVIEW_REQUIRED": "🟡", "REJECTED": "🔴"}.get(decision, "⚪")
        rows.append(
            f"| {fname} | {data.get('cosine_score', 0.0)} | "
            f"{data.get('validation_status', 'unknown')} | "
            f"{icon} {decision} | {data.get('translation_time_sec', 0)}s |"
        )

    notes_block = "\n".join(f"- {n}" for n in all_notes)

    content = f"""# ClinTranslate v4 — Pipeline Run Summary
**Run Timestamp:** {ts}  
**Tool:** ClinTranslate v4 Agentic (LangGraph 5-Agent Pipeline)

---

## Run Statistics
| Metric | Value |
|---|---|
| Total Programs Processed | {total} |
| 🟢 Auto-Approved | {approved} |
| 🟡 Review Required | {review} |
| 🔴 Rejected | {rejected} |
| Total SAS LOC Processed | {total_sas_loc} |
| Total Agent Runtime | {round(total_time_sec, 1)}s |
| Avg Cosine Score | {round(avg_score, 3)} |
| Estimated Time Saved | {round(total_saved, 2)} hrs vs {round(MANUAL_ESTIMATE_HOURS * total, 1)} hrs manual |
| Avg % Time Reduction | {avg_pct_saved}% |

---

## Execution Order (Dependency-Resolved)
{chr(10).join(f"{i+1}. {f}" for i, f in enumerate(execution_order))}

---

## Per-Program Results
| File | Score | Validation | Decision | Time |
|---|---|---|---|---|
{chr(10).join(rows)}

---

## Agent Log
{notes_block}

---

## Time Gain Story (Interview/LinkedIn Ready)
> *"On a {total}-program batch using BioMarin SDTM patterns, ClinTranslate v4 reduced average 
> translation time from ~{MANUAL_ESTIMATE_HOURS} hours to under {round(total_time_sec/total/60, 0) if total > 0 else 0} minutes per program — 
> an estimated {avg_pct_saved}% reduction — with {approved} of {total} programs auto-approved 
> and {review} flagged for lightweight review."*

---
*ClinTranslate v4 | github.com/ravinsun/clintranslate*
"""

    with open(path, "w") as f:
        f.write(content)

    return path


def run_report_generator(state: ReportState) -> ReportState:
    """
    LangGraph node: Writes benchmark CSV, per-file reports, and summary.
    """
    report_paths = []
    all_notes = (
        state.get("planner_notes", [])
        + state.get("translator_notes", [])
        + state.get("validator_notes", [])
        + state.get("scorer_notes", [])
    )

    # 1. Benchmark CSV
    csv_path = write_benchmark_csv(state["translations"])
    report_paths.append(csv_path)

    # 2. Per-file validation reports + Python output files
    for filename, data in state["translations"].items():
        rpt_path = write_validation_report(filename, data)
        report_paths.append(rpt_path)

        # Write translated Python file
        if data.get("python_code"):
            stem = Path(filename).stem
            py_path = os.path.join(REPORTS_DIR, f"{stem}_translated.py")
            with open(py_path, "w") as f:
                f.write(data["python_code"])
            report_paths.append(py_path)

    # 3. Pipeline summary
    summary_path = write_pipeline_summary(
        state["translations"],
        state.get("execution_order", []),
        all_notes,
    )
    report_paths.append(summary_path)

    state["report_paths"] = report_paths
    return state
