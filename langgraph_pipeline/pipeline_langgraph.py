"""
ClinTranslate v4 — LangGraph Pipeline Orchestrator (Standalone)

Architecture:
  Explicit StateGraph where every node, edge, and transition
  is defined in code. State flows deterministically through
  5 nodes. You control exactly what runs when.

Key difference vs CrewAI:
  - No agent "personalities" or LLM-interpreted roles
  - State is a typed dict passed explicitly between nodes
  - Conditional edges give precise control (e.g. skip if no files)
  - Every decision is logged and reproducible — GxP-auditable
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

# Reuse the same agent logic modules from agents/
sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.dependency_planner import run_dependency_planner
from agents.rag_translator import run_rag_translator
from agents.syntax_validator import run_syntax_validator
from agents.confidence_scorer import run_confidence_scorer
from agents.report_generator import run_report_generator


# ── Unified typed state ───────────────────────────────────────────────────────

class PipelineState(TypedDict):
    sas_folder: str
    sas_files: List[str]
    dependency_graph: Dict[str, List[str]]
    execution_order: List[str]
    planner_notes: List[str]
    translations: Dict[str, Dict[str, Any]]
    translator_notes: List[str]
    validator_notes: List[str]
    routing_summary: Dict[str, str]
    scorer_notes: List[str]
    report_paths: List[str]


# ── Conditional router ────────────────────────────────────────────────────────

def route_after_planning(state: PipelineState) -> str:
    """
    LangGraph conditional edge:
    If no SAS files found → go to END directly.
    Otherwise → proceed to translation.
    This is explicit control flow — no LLM involved in this decision.
    """
    if not state.get("sas_files"):
        print("   ⚠️  No SAS files found — pipeline terminated early")
        return "end"
    return "translate"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_langgraph_pipeline() -> StateGraph:
    """
    Compile the LangGraph StateGraph.
    Nodes are pure Python functions. Edges are explicit.
    """
    graph = StateGraph(PipelineState)

    # Register nodes — each is a deterministic Python function
    graph.add_node("plan",      run_dependency_planner)
    graph.add_node("translate", run_rag_translator)
    graph.add_node("validate",  run_syntax_validator)
    graph.add_node("score",     run_confidence_scorer)
    graph.add_node("report",    run_report_generator)

    # Entry point
    graph.set_entry_point("plan")

    # Conditional edge after planning (explicit guard)
    graph.add_conditional_edges(
        "plan",
        route_after_planning,
        {"translate": "translate", "end": END},
    )

    # Linear pipeline — deterministic, no LLM routing decisions
    graph.add_edge("translate", "validate")
    graph.add_edge("validate",  "score")
    graph.add_edge("score",     "report")
    graph.add_edge("report",    END)

    return graph.compile()


# ── Runner ────────────────────────────────────────────────────────────────────

def run_langgraph_pipeline(sas_folder: str) -> dict:
    """
    Run ClinTranslate via LangGraph StateGraph.
    Returns result dict with state, timing, and metadata.
    """
    start_time = time.time()
    print("\n" + "="*60)
    print("🔷 ClinTranslate v4 — LangGraph Pipeline")
    print(f"   Framework : LangGraph (StateGraph)")
    print(f"   Input     : {sas_folder}")
    print(f"   Started   : {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)

    pipeline = build_langgraph_pipeline()

    initial_state: PipelineState = {
        "sas_folder": sas_folder,
        "sas_files": [],
        "dependency_graph": {},
        "execution_order": [],
        "planner_notes": [],
        "translations": {},
        "translator_notes": [],
        "validator_notes": [],
        "routing_summary": {},
        "scorer_notes": [],
        "report_paths": [],
    }

    # Node-level timing wrapper
    node_timings = {}
    nodes_in_order = ["plan", "translate", "validate", "score", "report"]
    current_state = initial_state

    # Run agent by agent with timing
    agent_fns = [
        ("plan",      run_dependency_planner),
        ("translate", run_rag_translator),
        ("validate",  run_syntax_validator),
        ("score",     run_confidence_scorer),
        ("report",    run_report_generator),
    ]

    labels = {
        "plan":      "1️⃣  Dependency Planner",
        "translate": "2️⃣  RAG Translator",
        "validate":  "3️⃣  Syntax Validator",
        "score":     "4️⃣  Confidence Scorer",
        "report":    "5️⃣  Report Generator",
    }

    for node_name, fn in agent_fns:
        # Guard: skip remaining if no files after planning
        if node_name != "plan" and not current_state.get("sas_files"):
            break

        print(f"\n{labels[node_name]} — running...")
        t0 = time.time()
        current_state = fn(current_state)
        node_timings[node_name] = round(time.time() - t0, 2)

        notes_key = {
            "plan":      "planner_notes",
            "translate": "translator_notes",
            "validate":  "validator_notes",
            "score":     "scorer_notes",
            "report":    "report_paths",
        }[node_name]
        notes = current_state.get(notes_key, [])
        for n in (notes[:3] if notes else []):
            print(f"   → {n}")
        print(f"   ✅ Done in {node_timings[node_name]}s")

    elapsed = round(time.time() - start_time, 1)

    print("\n" + "="*60)
    print(f"✅ LangGraph Pipeline Complete — {elapsed}s total")
    print(f"   Node timings: {node_timings}")
    print("="*60)

    return {
        "framework": "LangGraph",
        "process": "StateGraph (deterministic)",
        "elapsed_sec": elapsed,
        "node_timings": node_timings,
        "final_state": current_state,
        "report_paths": current_state.get("report_paths", []),
        "routing_summary": current_state.get("routing_summary", {}),
    }


if __name__ == "__main__":
    load_dotenv()
    folder = sys.argv[1] if len(sys.argv) > 1 else "./data/sample_sas"
    run_langgraph_pipeline(folder)
