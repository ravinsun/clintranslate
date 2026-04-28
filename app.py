import streamlit as st
from rag_engine import translate_sas_to_python

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="ClinTranslate",
    page_icon="🧬",
    layout="wide"
)

# ── Styling ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0a0e1a; }
    .stTextArea textarea {
        font-family: 'Courier New', monospace;
        font-size: 13px;
        background-color: #0d1117;
        color: #c9d1d9;
        border: 1px solid #1e6a4a;
    }
    .stButton button {
        background: linear-gradient(135deg, #1e6a4a, #16a34a);
        color: white;
        font-weight: 600;
        letter-spacing: 1px;
        border: none;
        padding: 10px 30px;
        width: 100%;
    }
    .stButton button:hover { opacity: 0.85; }
    code { font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────
st.markdown("## 🧬 ClinTranslate — SAS → Python")
st.markdown("*RAG-powered clinical data code translator · HuggingFace + ChromaDB + Claude*")
st.divider()

# ── Examples sidebar ──────────────────────────────────────────────────
EXAMPLES = {
    "PROC SORT": "PROC SORT DATA=adlb OUT=adlb_sorted;\n  BY USUBJID PARAMCD VISITNUM;\nRUN;",
    "PROC MEANS": "PROC MEANS DATA=adlb N MEAN STD MIN MAX;\n  CLASS TRTA PARAMCD;\n  VAR AVAL;\nRUN;",
    "DATA Step Merge": "DATA adsl_adlb;\n  MERGE adsl(IN=a) adlb(IN=b);\n  BY USUBJID;\n  IF a AND b;\nRUN;",
    "Change from Baseline": "DATA adlb_chg;\n  SET adlb;\n  BY USUBJID PARAMCD;\n  IF FIRST.PARAMCD THEN base=AVAL;\n  RETAIN base;\n  CHG=AVAL-base;\nRUN;",
    "PROC FREQ": "PROC FREQ DATA=adae;\n  TABLES TRTA*AEDECOD / CHISQ;\n  WHERE TRTEMFL='Y';\nRUN;",
}

with st.sidebar:
    st.markdown("### 📋 Quick Examples")
    for label, code in EXAMPLES.items():
        if st.button(label, key=label):
            st.session_state["sas_input"] = code

    st.divider()
    st.markdown("### ℹ️ How it works")
    st.markdown("""
1. Your SAS code is **embedded** via HuggingFace
2. **ChromaDB** retrieves the most similar translation pairs
3. Retrieved context + your code sent to **Claude**
4. Claude returns clean Python + translation notes
    """)

# ── Main layout ───────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### SAS Input")
    sas_code = st.text_area(
        label="sas_input",
        value=st.session_state.get("sas_input", ""),
        height=350,
        placeholder="Paste your SAS code here or pick an example →",
        label_visibility="collapsed"
    )

    translate = st.button("⟶ Translate to Python", use_container_width=True)

with col2:
    st.markdown("#### Python Output")

    if translate:
        if not sas_code.strip():
            st.warning("Please enter some SAS code first.")
        else:
            with st.spinner("Retrieving context from ChromaDB + translating with Claude..."):
                try:
                    result = translate_sas_to_python(sas_code)

                    # Python code
                    st.code(result["python_code"], language="python")

                    # Translation notes
                    if result["notes"]:
                        st.markdown("**📝 Translation Notes:**")
                        for note in result["notes"]:
                            st.markdown(f"- {note}")

                    # RAG context expander
                    with st.expander("🔍 Retrieved RAG Context"):
                        st.text(result["context_used"])

                except Exception as e:
                    st.error(f"Error: {str(e)}")
    else:
        st.info("Output will appear here after translation.")
