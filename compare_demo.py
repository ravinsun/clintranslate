"""
ClinTranslate — Framework Comparison Demo
Runs both CrewAI and LangGraph pipelines on the same SAS folder,
then produces a side-by-side analysis report.

Usage:
    python compare_demo.py ./data/sample_sas [--framework crewai|langgraph|both]

Output:
    reports/framework_comparison_<timestamp>.md
"""

import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ── Comparison report writer ──────────────────────────────────────────────────

def write_comparison_report(lg_result: dict, ca_result: dict, sas_folder: str) -> str:
    """
    Generate a side-by-side markdown comparison of LangGraph vs CrewAI.
    """
    os.makedirs("reports", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"reports/framework_comparison_{ts}.md"

    lg_time = lg_result.get("elapsed_sec", "N/A")
    ca_time = ca_result.get("elapsed_sec", "N/A")
    lg_routing = lg_result.get("routing_summary", {})
    lg_node_timings = lg_result.get("node_timings", {})

    # Per-node timing table for LangGraph
    node_rows = "\n".join(
        f"| {name.capitalize()} | {t}s |"
        for name, t in lg_node_timings.items()
    ) if lg_node_timings else "| N/A | N/A |"

    # Routing summary for LangGraph
    routing_rows = "\n".join(
        f"| {fname} | {decision} |"
        for fname, decision in lg_routing.items()
    ) if lg_routing else "| N/A | N/A |"

    content = f"""# ClinTranslate — Framework Comparison Report
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Input Folder:** {sas_folder}  
**SAS Files Processed:** {len(lg_routing) if lg_routing else 'N/A'}

---

## 1. Architecture Comparison

| Dimension | 🔷 LangGraph | 🤖 CrewAI |
|---|---|---|
| **Mental Model** | State machine — explicit graph of nodes + edges | Agent crew — roles, goals, backstories |
| **Control Flow** | You define every edge in code | CrewAI + LLM decide delegation |
| **State Management** | Typed `PipelineState` dict passed explicitly | Task output passed via `context=[]` |
| **Determinism** | ✅ High — same input → same path every time | ⚠️ Medium — LLM interprets roles |
| **Auditability** | ✅ Every node timed, every decision logged | ⚠️ Agent reasoning partially opaque |
| **GxP Fit** | ✅ Excellent — reproducible, inspectable | ⚠️ Needs extra validation wrapper |
| **Self-Correction** | Explicit retry loop (max 2, coded) | Agent autonomously decides when to retry |
| **Conditional Routing** | `add_conditional_edges()` — pure Python | Agent delegation — LLM-driven |
| **Best For** | Fixed-stage regulated pipelines | Open-ended collaborative tasks |
| **Verbosity** | Medium — code-first | High — LLM reasoning visible in logs |

---

## 2. Runtime Comparison

| Metric | 🔷 LangGraph | 🤖 CrewAI |
|---|---|---|
| Total Runtime | {lg_time}s | {ca_time}s |
| Framework Overhead | Low (pure Python graph) | Higher (LLM interprets each agent role) |
| API Calls (approx) | 1 per translation + 1 per correction | 1 per task + role interpretation overhead |
| Token Usage | Focused (task-specific prompts) | Higher (role/goal/backstory in every call) |

---

## 3. LangGraph — Per-Node Timing

| Node | Time |
|---|---|
{node_rows}

---

## 4. LangGraph — Routing Decisions

| File | Decision |
|---|---|
{routing_rows}

---

## 5. Code Architecture Comparison

### LangGraph — How the graph is wired
```python
graph = StateGraph(PipelineState)           # typed state
graph.add_node("plan",      run_planner)    # pure Python function
graph.add_node("translate", run_translator)
graph.add_node("validate",  run_validator)
graph.add_node("score",     run_scorer)
graph.add_node("report",    run_reporter)

graph.set_entry_point("plan")
graph.add_conditional_edges(               # explicit routing logic
    "plan",
    lambda s: "translate" if s["sas_files"] else "end",
    {{"translate": "translate", "end": END}},
)
graph.add_edge("translate", "validate")    # deterministic flow
graph.add_edge("validate",  "score")
graph.add_edge("score",     "report")
graph.add_edge("report",    END)
pipeline = graph.compile()
```

### CrewAI — How the crew is assembled
```python
planner = Agent(
    role="SAS Dependency Analyst",
    goal="Resolve %INCLUDE dependencies and produce execution order",
    backstory="20-year SAS architect in pharma...",
    llm=llm,
)
t1 = Task(description="Scan {folder}...", agent=planner)
t2 = Task(description="Translate each file...", agent=translator, context=[t1])
t3 = Task(description="Validate syntax...", agent=validator, context=[t2])

crew = Crew(
    agents=[planner, translator, validator, scorer, reporter],
    tasks=[t1, t2, t3, t4, t5],
    process=Process.sequential,
)
result = crew.kickoff()   # CrewAI manages context passing
```

---

## 6. When to Choose Which

### Choose LangGraph when:
- ✅ The pipeline has **fixed, known stages** (SDTM → ADaM → TLF)
- ✅ **GxP / regulatory context** — you need reproducible, auditable runs
- ✅ You want **per-node timing and logging** for validation documentation
- ✅ **Self-correction needs bounded retries** (max N — not open-ended)
- ✅ You need **conditional routing** based on data (not LLM judgment)
- ✅ Production clinical data pipelines

### Choose CrewAI when:
- ✅ Tasks are **open-ended** (research, literature review, report drafting)
- ✅ You want agents to **collaborate and delegate** autonomously
- ✅ **Exploratory workflows** where the path isn't fully known upfront
- ✅ **Rapid prototyping** — less boilerplate than LangGraph
- ✅ Non-regulated environments where LLM autonomy is acceptable

---

## 7. Interview / LinkedIn Framing

> *"I built ClinTranslate in two agentic architectures — LangGraph for the 
> production GxP pipeline (deterministic, auditable, bounded retries) and 
> CrewAI for an experimental collaborative version — and I can articulate 
> exactly why each framework fits a different class of problem."*

---

## 8. ClinTranslate Reports
"""

    lg_reports = lg_result.get("report_paths", [])
    if lg_reports:
        content += "\n**LangGraph outputs:**\n"
        for r in lg_reports:
            content += f"- `{r}`\n"

    ca_report = ca_result.get("report_path", "")
    if ca_report:
        content += f"\n**CrewAI output:**\n- `{ca_report}`\n"

    content += "\n---\n*ClinTranslate | github.com/ravinsun/clintranslate*\n"

    with open(path, "w") as f:
        f.write(content)

    return path


# ── Main runner ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ClinTranslate Framework Comparison Demo")
    parser.add_argument("folder", nargs="?", default="./data/sample_sas",
                        help="Folder containing .sas files")
    parser.add_argument("--framework", choices=["crewai", "langgraph", "both"],
                        default="both", help="Which framework to run")
    args = parser.parse_args()

    if not os.path.isdir(args.folder):
        print(f"❌ Folder not found: {args.folder}")
        sys.exit(1)

    print("\n" + "█"*60)
    print("  ClinTranslate — Framework Comparison Demo")
    print("  LangGraph (StateGraph) vs CrewAI (Agent Crew)")
    print("█"*60)

    lg_result = {"framework": "LangGraph", "elapsed_sec": 0, "routing_summary": {}, "report_paths": [], "node_timings": {}}
    ca_result = {"framework": "CrewAI",    "elapsed_sec": 0, "report_path": ""}

    # ── Run LangGraph ─────────────────────────────────────────────────────────
    if args.framework in ("langgraph", "both"):
        try:
            from langgraph_pipeline.pipeline_langgraph import run_langgraph_pipeline
            lg_result = run_langgraph_pipeline(args.folder)
        except Exception as e:
            print(f"\n❌ LangGraph pipeline error: {e}")
            lg_result["error"] = str(e)

    # Brief pause between frameworks for clean log separation
    if args.framework == "both":
        print("\n⏸️  Pausing 2s before CrewAI run...\n")
        time.sleep(2)

    # ── Run CrewAI ────────────────────────────────────────────────────────────
    if args.framework in ("crewai", "both"):
        try:
            from crewai_pipeline.pipeline_crewai import run_crewai_pipeline
            ca_result = run_crewai_pipeline(args.folder)
        except ImportError:
            print("\n⚠️  CrewAI not installed. Run: pip install crewai langchain-anthropic")
            ca_result["error"] = "crewai not installed"
        except Exception as e:
            print(f"\n❌ CrewAI pipeline error: {e}")
            ca_result["error"] = str(e)

    # ── Write comparison report ───────────────────────────────────────────────
    report_path = write_comparison_report(lg_result, ca_result, args.folder)

    print("\n" + "█"*60)
    print("  COMPARISON COMPLETE")
    print(f"  🔷 LangGraph : {lg_result.get('elapsed_sec', 'N/A')}s")
    print(f"  🤖 CrewAI    : {ca_result.get('elapsed_sec', 'N/A')}s")
    print(f"  📄 Report    : {report_path}")
    print("█"*60 + "\n")


if __name__ == "__main__":
    main()
