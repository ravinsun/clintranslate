"""
ClinTranslate — Framework Comparison Streamlit UI
Run: streamlit run app_compare.py
"""

import os
import sys
import time
import tempfile
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="ClinTranslate — Framework Comparison",
    page_icon="🧬",
    layout="wide",
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🧬 ClinTranslate — LangGraph vs CrewAI")
st.caption("Same 5-agent clinical SAS→Python pipeline. Two agentic frameworks. Side-by-side comparison.")

col_lg, col_ca = st.columns(2)
with col_lg:
    st.markdown("### 🔷 LangGraph")
    st.caption("StateGraph · Deterministic · GxP-auditable · Explicit edges")
with col_ca:
    st.markdown("### 🤖 CrewAI")
    st.caption("Agent Crew · Role-based · Collaborative · LLM-interpreted")

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input(
        "Anthropic API Key", value=os.getenv("ANTHROPIC_API_KEY", ""), type="password"
    )
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    st.divider()
    framework_choice = st.radio(
        "Run which framework?",
        ["Both (comparison)", "LangGraph only", "CrewAI only"],
        index=0,
    )

    st.divider()
    st.markdown("**Why LangGraph for GxP?**")
    st.markdown("- Deterministic execution order")
    st.markdown("- Bounded self-correction (max 2 retries)")
    st.markdown("- Per-node timing → auditable")
    st.markdown("- Conditional edges in code, not LLM")

    st.markdown("**Why CrewAI for exploration?**")
    st.markdown("- Agents collaborate autonomously")
    st.markdown("- Role + backstory = richer context")
    st.markdown("- Less boilerplate for open-ended tasks")
    st.markdown("- Better for non-regulated workflows")

# ── File upload ───────────────────────────────────────────────────────────────
st.subheader("📁 Upload SAS Files")
uploaded_files = st.file_uploader(
    "Upload .sas files to translate",
    type=["sas"],
    accept_multiple_files=True,
)

run_btn = st.button(
    "🚀 Run Pipeline(s)",
    disabled=not uploaded_files or not api_key,
    type="primary",
)

# ── Runner ────────────────────────────────────────────────────────────────────
if run_btn and uploaded_files:

    tmp_dir = tempfile.mkdtemp()
    for uf in uploaded_files:
        with open(os.path.join(tmp_dir, uf.name), "wb") as f:
            f.write(uf.read())

    st.info(f"📂 {len(uploaded_files)} file(s) ready — launching pipeline(s)...")

    run_lg = framework_choice in ("Both (comparison)", "LangGraph only")
    run_ca = framework_choice in ("Both (comparison)", "CrewAI only")

    lg_result = {}
    ca_result = {}

    # ── LangGraph run ─────────────────────────────────────────────────────────
    if run_lg:
        with st.expander("🔷 LangGraph — Live Agent Progress", expanded=True):
            st.markdown("**Running 5-agent StateGraph...**")

            agent_names = [
                ("1️⃣", "Dependency Planner",  "planner_notes"),
                ("2️⃣", "RAG Translator",       "translator_notes"),
                ("3️⃣", "Syntax Validator",     "validator_notes"),
                ("4️⃣", "Confidence Scorer",    "scorer_notes"),
                ("5️⃣", "Report Generator",     "report_paths"),
            ]

            from agents.dependency_planner import run_dependency_planner
            from agents.rag_translator import run_rag_translator
            from agents.syntax_validator import run_syntax_validator
            from agents.confidence_scorer import run_confidence_scorer
            from agents.report_generator import run_report_generator

            agent_fns = [
                run_dependency_planner,
                run_rag_translator,
                run_syntax_validator,
                run_confidence_scorer,
                run_report_generator,
            ]

            state = {
                "sas_folder": tmp_dir, "sas_files": [], "dependency_graph": {},
                "execution_order": [], "planner_notes": [], "translations": {},
                "translator_notes": [], "validator_notes": [], "routing_summary": {},
                "scorer_notes": [], "report_paths": [],
            }

            lg_total_start = time.time()
            node_timings = {}
            pb = st.progress(0)

            for i, (fn, (icon, label, notes_key)) in enumerate(zip(agent_fns, agent_names)):
                if i > 0 and not state.get("sas_files"):
                    st.warning("⚠️ No SAS files — pipeline stopped")
                    break

                status_placeholder = st.empty()
                status_placeholder.markdown(f"{icon} **{label}** — 🔄 Running...")
                t0 = time.time()
                state = fn(state)
                elapsed = round(time.time() - t0, 2)
                node_timings[label] = elapsed

                notes = state.get(notes_key, [])
                note_lines = "\n".join(f"  → {n}" for n in (notes[:2] if isinstance(notes, list) and notes and isinstance(notes[0], str) else []))
                status_placeholder.markdown(f"{icon} **{label}** — ✅ {elapsed}s\n{note_lines}")
                pb.progress((i + 1) / len(agent_fns))

            lg_elapsed = round(time.time() - lg_total_start, 1)
            st.success(f"✅ LangGraph complete — {lg_elapsed}s total")

            lg_result = {
                "framework": "LangGraph",
                "elapsed_sec": lg_elapsed,
                "node_timings": node_timings,
                "routing_summary": state.get("routing_summary", {}),
                "translations": state.get("translations", {}),
                "report_paths": state.get("report_paths", []),
            }

    # ── CrewAI run ────────────────────────────────────────────────────────────
    if run_ca:
        with st.expander("🤖 CrewAI — Agent Crew", expanded=True):
            st.markdown("**Assembling 5-agent crew...**")
            ca_progress = st.empty()
            ca_progress.info("🤖 CrewAI crew running — agents collaborating via role+goal+backstory...")

            ca_start = time.time()
            try:
                from crewai_pipeline.pipeline_crewai import run_crewai_pipeline
                ca_result = run_crewai_pipeline(tmp_dir)
                ca_elapsed = round(time.time() - ca_start, 1)
                ca_progress.success(f"✅ CrewAI complete — {ca_elapsed}s total")
                st.markdown("**CrewAI Output:**")
                st.markdown(ca_result.get("raw_output", "")[:3000] + "...")
            except ImportError:
                ca_progress.error("⚠️ CrewAI not installed: `pip install crewai langchain-anthropic`")
                ca_result = {"framework": "CrewAI", "elapsed_sec": 0, "error": "not installed"}
            except Exception as e:
                ca_progress.error(f"❌ CrewAI error: {e}")
                ca_result = {"framework": "CrewAI", "elapsed_sec": 0, "error": str(e)}

    # ── Side-by-side results ──────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Side-by-Side Comparison")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### 🔷 LangGraph Results")
        if lg_result:
            st.metric("Total Runtime", f"{lg_result.get('elapsed_sec', 0)}s")

            timings = lg_result.get("node_timings", {})
            if timings:
                st.markdown("**Per-Node Timing:**")
                for node, t in timings.items():
                    st.caption(f"  {node}: {t}s")

            routing = lg_result.get("routing_summary", {})
            if routing:
                st.markdown("**Routing Decisions:**")
                for fname, decision in routing.items():
                    badge = {"AUTO_APPROVED": "🟢", "REVIEW_REQUIRED": "🟡", "REJECTED": "🔴"}.get(decision, "⚪")
                    st.caption(f"  {badge} {fname} → {decision}")

            translations = lg_result.get("translations", {})
            if translations:
                for fname, data in translations.items():
                    with st.expander(f"📄 {fname} — translated Python"):
                        st.code(data.get("python_code", ""), language="python")

    with c2:
        st.markdown("### 🤖 CrewAI Results")
        if ca_result:
            st.metric("Total Runtime", f"{ca_result.get('elapsed_sec', 0)}s")
            if ca_result.get("error"):
                st.error(f"Error: {ca_result['error']}")
            elif ca_result.get("raw_output"):
                st.markdown(ca_result["raw_output"][:2000])

    # ── Architecture callout ──────────────────────────────────────────────────
    st.divider()
    st.subheader("🏗️ Architecture Difference")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**LangGraph — Explicit State Machine**")
        st.code("""graph = StateGraph(PipelineState)
graph.add_node("plan",      run_planner)
graph.add_node("translate", run_translator)
graph.add_conditional_edges(
    "plan",
    lambda s: "translate" if s["sas_files"] else "end"
)
graph.add_edge("translate", "validate")
# You control every transition""", language="python")

    with c4:
        st.markdown("**CrewAI — Role-Based Agent Crew**")
        st.code("""planner = Agent(
    role="SAS Dependency Analyst",
    goal="Resolve %INCLUDE dependencies...",
    backstory="20-year SAS architect in pharma...",
)
crew = Crew(
    agents=[planner, translator, ...],
    tasks=[t1, t2, ...],
    process=Process.sequential,
)
# CrewAI manages context passing""", language="python")

    # ── Download reports ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📥 Download Reports")
    for rpath in lg_result.get("report_paths", []):
        if os.path.isfile(rpath):
            with open(rpath, "rb") as f:
                st.download_button(
                    f"⬇️ [LangGraph] {Path(rpath).name}",
                    data=f.read(),
                    file_name=Path(rpath).name,
                    mime="text/plain",
                )
    ca_report = ca_result.get("report_path", "")
    if ca_report and os.path.isfile(ca_report):
        with open(ca_report, "rb") as f:
            st.download_button(
                f"⬇️ [CrewAI] {Path(ca_report).name}",
                data=f.read(),
                file_name=Path(ca_report).name,
                mime="text/markdown",
            )
