"""
app_compare.py  —  ClinTranslate Framework Comparison Dashboard
Reads results/lg_result.json and results/ca_result.json
and displays a side-by-side visual comparison.

Run after both pipelines complete:
    streamlit run app_compare.py
"""

import os
import json
from pathlib import Path
from datetime import datetime

import streamlit as st

st.set_page_config(
    page_title="ClinTranslate — Framework Comparison",
    page_icon="🧬",
    layout="wide",
)

def load_result(path):
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return None

def routing_badge(decision):
    return {"AUTO_APPROVED": "🟢", "REVIEW_REQUIRED": "🟡", "REJECTED": "🔴"}.get(decision, "⚪")

st.title("🧬 ClinTranslate — Framework Comparison")
st.caption("LangGraph (StateGraph) vs CrewAI (Agent Crew) — same 5 agents, same clinical SAS→Python task")

lg = load_result("results/lg_result.json")
ca = load_result("results/ca_result.json")

if not lg and not ca:
    st.warning("No results found yet. Run both pipelines first:")
    st.code("""# Step 1 — LangGraph (venv311)
source venv311/bin/activate
python3 run_langgraph.py ./data/sample_sas

# Step 2 — CrewAI (venv311_crew)
source venv311_crew/bin/activate
PYTHONPATH=. python3 run_crewai.py ./data/sample_sas

# Step 3 — View comparison
source venv311/bin/activate
streamlit run app_compare.py""")
    st.stop()

# Run info
col1, col2 = st.columns(2)
if lg:
    col1.info(f"🔷 LangGraph: {lg.get('run_timestamp','—')} | {lg.get('elapsed_sec')}s | {lg.get('file_count')} files")
if ca:
    col2.info(f"🤖 CrewAI: {ca.get('run_timestamp','—')} | {ca.get('elapsed_sec')}s | {ca.get('file_count')} files")

st.divider()

# Top metrics
st.subheader("📊 Head-to-Head")

m = st.columns(6)
lg_ppf = round(lg["elapsed_sec"]/lg["file_count"],1) if lg and lg.get("file_count") else "—"
ca_ppf = round(ca["elapsed_sec"]/ca["file_count"],1) if ca and ca.get("file_count") else "—"

rows = [
    ("Files",          lg["file_count"] if lg else "—",           ca["file_count"] if ca else "—"),
    ("Total (s)",      lg["elapsed_sec"] if lg else "—",           ca["elapsed_sec"] if ca else "—"),
    ("Per file (s)",   lg_ppf,                                     ca_ppf),
    ("Avg cosine",     lg["stats"]["avg_cosine"] if lg else "—",   ca["stats"]["avg_cosine"] if ca else "—"),
    ("Syntax valid",   f"{lg['stats']['syntax_valid']}/{lg['file_count']}" if lg else "—",
                       f"{ca['stats']['syntax_valid']}/{ca['file_count']}" if ca else "—"),
    ("TFL flagged",    lg["stats"]["tfl_flagged"] if lg else "—",  ca["stats"]["tfl_flagged"] if ca else "—"),
]
for i,(label,lv,cv) in enumerate(rows):
    with m[i]:
        st.metric(label, lv)
        st.caption(f"🤖 {cv}")

st.divider()

# Side by side
left, right = st.columns(2)

with left:
    st.markdown("### 🔷 LangGraph")
    if not lg:
        st.warning("Run `python3 run_langgraph.py ./data/sample_sas` first")
    else:
        s = lg["stats"]
        r1,r2,r3 = st.columns(3)
        r1.metric("🟢 Auto", s["auto_approved"])
        r2.metric("🟡 Review", s["review_required"])
        r3.metric("🔴 Rejected", s["rejected"])

        if lg.get("node_timings"):
            st.markdown("**Node timings**")
            for node, t in lg["node_timings"].items():
                pct = min(int((t / lg["elapsed_sec"]) * 100), 100) if lg["elapsed_sec"] else 0
                st.progress(pct/100, text=f"{node}: {t}s")

        st.markdown("**Per-file results**")
        for t in lg["translations"]:
            badge = routing_badge(t["routing_decision"])
            tfl = " ⚠️TFL" if t["tfl_flagged"] else ""
            with st.expander(f"{badge} {t['filename']}{tfl}"):
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Score", t["cosine_score"])
                c2.metric("Syntax", t["validation_status"].upper()[:7])
                c3.metric("SAS LOC", t["sas_loc"])
                c4.metric("Py LOC", t["py_loc"])
                st.caption(f"⏱ {t['translation_time']}s | {t['routing_decision']}")
                if t.get("routing_reason"):
                    st.caption(f"📝 {t['routing_reason']}")
                if t.get("python_code"):
                    code = t["python_code"]
                    st.code(code[:1500] + ("..." if len(code)>1500 else ""), language="python")

        st.info("✅ **Stateful** — typed dict, real ChromaDB, real ast.parse()")

with right:
    st.markdown("### 🤖 CrewAI")
    if not ca:
        st.warning("Run `PYTHONPATH=. python3 run_crewai.py ./data/sample_sas` first")
    else:
        s = ca["stats"]
        r1,r2,r3 = st.columns(3)
        r1.metric("🟢 Auto", s["auto_approved"])
        r2.metric("🟡 Review", s["review_required"])
        r3.metric("🔴 Rejected", s["rejected"])

        st.markdown("**Agent roles**")
        roles = [
            ("SAS Dependency Analyst",            "Scans %INCLUDE, builds execution order"),
            ("Clinical SAS-to-Python Translator",  "RAG + Claude translation"),
            ("Python Code Quality Validator",       "Syntax check + self-correction"),
            ("Translation Confidence Assessor",     "Routes by cosine score"),
            ("Validation Report Author",            "GxP reports + reviewer checklists"),
        ]
        for role, desc in roles:
            st.caption(f"**{role}** — {desc}")

        if ca["translations"]:
            st.markdown("**Parsed results**")
            for t in ca["translations"]:
                badge = routing_badge(t["routing_decision"])
                with st.expander(f"{badge} {t['filename']}"):
                    c1,c2 = st.columns(2)
                    c1.metric("Score", t["cosine_score"] or "LLM-est.")
                    c2.metric("Decision", t["routing_decision"])
        else:
            st.markdown("**CrewAI narrative output**")
            raw = ca.get("raw_output","")
            st.markdown(raw[:3000] + ("..." if len(raw)>3000 else ""))

        st.warning("⚠️ **Context-passing** — text between agents, scores LLM-estimated")

# Architecture code
st.divider()
st.subheader("🏗️ Key Code Difference")

a1,a2 = st.columns(2)
with a1:
    st.markdown("**LangGraph — explicit edges**")
    st.code("""graph.add_edge("translate", "validate")
graph.add_conditional_edges(
    "plan",
    lambda s: "translate" if s["sas_files"] else "end"
)
# You define every transition in code""", language="python")

with a2:
    st.markdown("**CrewAI — context chain**")
    st.code("""t3 = Task(
    description="Validate syntax...",
    context=[t2],  # prior task output as text
    agent=validator_agent,
)
# LLM interprets the context""", language="python")

# Comparison table
st.divider()
st.subheader("🔑 Framework Decision Guide")

import pandas as pd
df = pd.DataFrame({
    "Dimension":    ["State","Scores","Validation","GxP fit","Speed/file","Best for"],
    "🔷 LangGraph": ["Typed Python dict","Real ChromaDB","Real ast.parse()","✅ Excellent","55s","Regulated pipelines"],
    "🤖 CrewAI":    ["Text context","LLM-estimated","LLM-described","⚠️ Limited","89s","Open-ended tasks"],
})
st.dataframe(df, use_container_width=True, hide_index=True)

# Downloads
st.divider()
st.subheader("📥 Download")
d1,d2 = st.columns(2)
with d1:
    if lg:
        st.download_button("⬇️ LangGraph JSON", json.dumps(lg,indent=2),
                           "lg_result.json","application/json")
        for rpath in lg.get("report_paths",[]):
            if os.path.isfile(rpath):
                with open(rpath,"rb") as f:
                    st.download_button(f"⬇️ {Path(rpath).name}",
                                       f.read(), Path(rpath).name, "text/plain")
with d2:
    if ca:
        safe = {k:v for k,v in ca.items() if k!="raw_output"}
        st.download_button("⬇️ CrewAI JSON", json.dumps(safe,indent=2),
                           "ca_result.json","application/json")
        rp = ca.get("report_path","")
        if rp and os.path.isfile(rp):
            with open(rp,"rb") as f:
                st.download_button(f"⬇️ {Path(rp).name}",
                                   f.read(), Path(rp).name,"text/markdown")
