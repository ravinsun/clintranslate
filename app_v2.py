import streamlit as st
from rag_engine_v2 import (
    translate_sas, ingest_sas_file,
    ingest_github_repo, collection
)

st.set_page_config(
    page_title="ClinTranslate v2",
    page_icon="🧬",
    layout="wide"
)

st.markdown("""
<style>
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
        width: 100%;
    }
    .warning-box {
        background: #2d1b00;
        border-left: 4px solid #f97316;
        padding: 12px;
        border-radius: 4px;
        color: #fed7aa;
        margin: 10px 0;
    }
    .score-badge {
        background: #1e3a2a;
        border: 1px solid #16a34a;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 11px;
        color: #4ade80;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────
st.markdown("## 🧬 ClinTranslate v2")
st.markdown("*SAS-only RAG corpus · Claude generates Python or R from scratch*")
st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────
EXAMPLES = {
    "PROC SORT":     "PROC SORT DATA=adlb OUT=adlb_sorted;\n  BY USUBJID PARAMCD VISITNUM;\nRUN;",
    "PROC MEANS":    "PROC MEANS DATA=adlb N MEAN STD MIN MAX;\n  CLASS TRTA PARAMCD;\n  VAR AVAL;\nRUN;",
    "DATA Merge":    "DATA adsl_adlb;\n  MERGE adsl(IN=a) adlb(IN=b);\n  BY USUBJID;\n  IF a AND b;\nRUN;",
    "Baseline CHG":  "DATA adlb_chg;\n  SET adlb;\n  BY USUBJID PARAMCD;\n  IF FIRST.PARAMCD THEN base=AVAL;\n  RETAIN base;\n  CHG=AVAL-base;\nRUN;",
    "PROC MIXED":    "PROC MIXED DATA=adlb;\n  CLASS TRTA VISITNUM;\n  MODEL AVAL=TRTA VISITNUM TRTA*VISITNUM BASE / DDFM=KR;\n  REPEATED VISITNUM / SUBJECT=USUBJID TYPE=UN;\nRUN;",
    "KM Survival":   "PROC LIFETEST DATA=adtte PLOTS=SURVIVAL;\n  TIME AVAL*CNSR(1);\n  STRATA TRTA;\nRUN;",
}

with st.sidebar:
    st.markdown("### 📋 Quick Examples")
    for label, code in EXAMPLES.items():
        if st.button(label, key=label):
            st.session_state["sas_input"] = code

    st.divider()

    # ── Language selector
    st.markdown("### 🎯 Output Language")
    target_lang = st.radio(
        "Translate to:",
        ["Python (pandas/numpy)", "R (tidyverse/admiral)"],
        label_visibility="collapsed"
    )
    target_lang = "Python" if "Python" in target_lang else "R"

    st.divider()

    # ── GitHub ingestion
    st.markdown("### 🔗 Ingest GitHub Repo")
    github_url = st.text_input(
        "GitHub repo URL",
        placeholder="https://github.com/user/repo"
    )
    if st.button("📥 Ingest Repo"):
        if github_url:
            with st.spinner("Fetching .sas files from GitHub..."):
                count, message = ingest_github_repo(github_url)
                if count > 0:
                    st.success(message)
                else:
                    st.error(message)
        else:
            st.warning("Please enter a GitHub URL")

    st.divider()

    # ── KB stats
    total = collection.count()
    st.markdown(f"### 📊 Knowledge Base")
    st.metric("SAS programs indexed", total)
    st.markdown("""
### ℹ️ How v2 works
1. KB contains **SAS only** — no hand-written Python/R
2. ChromaDB retrieves **similar SAS patterns**
3. Claude **generates** Python or R from scratch
4. RAG provides **domain context** only
    """)

# ── Main layout ───────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["✏️ Paste Code", "📁 Upload .sas File"])

# ── Tab 1: Paste
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"#### SAS Input")
        sas_code = st.text_area(
            label="sas_code",
            value=st.session_state.get("sas_input", ""),
            height=320,
            placeholder="Paste SAS code here or pick an example →",
            label_visibility="collapsed"
        )
        translate_btn = st.button(
            f"⟶ Translate to {target_lang}",
            use_container_width=True,
            key="translate_paste"
        )

    with col2:
        st.markdown(f"#### {target_lang} Output")

        if translate_btn:
            if not sas_code.strip():
                st.warning("Please enter SAS code first.")
            else:
                with st.spinner(f"Retrieving SAS context → generating {target_lang}..."):
                    try:
                        result = translate_sas(sas_code, target_lang)

                        # TFL Warning
                        if result["tfl_warning"]:
                            st.markdown(
                                f'<div class="warning-box">⚠️ <strong>TFL Components Detected:</strong> '
                                f'{", ".join(result["tfl_warning"])}<br>'
                                f'Translation will be partial — manual review required for formatting logic.</div>',
                                unsafe_allow_html=True
                            )

                        # Code output
                        lang_display = "python" if target_lang == "Python" else "r"
                        st.code(result["code"], language=lang_display)

                        # Translation notes
                        if result["notes"]:
                            st.markdown("**📝 Translation Notes:**")
                            for note in result["notes"]:
                                st.markdown(f"- {note}")

                        # Similarity scores
                        st.markdown("**🎯 RAG Similarity Scores:**")
                        scores = result["similarity_scores"]
                        score_cols = st.columns(len(scores))
                        for i, (col, score) in enumerate(zip(score_cols, scores)):
                            col.metric(f"Match {i+1}", f"{score:.3f}")

                        # Retrieved context
                        with st.expander("🔍 Retrieved SAS Context (RAG)"):
                            st.text(result["context"])

                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        else:
            st.info(f"{target_lang} output will appear here after translation.")

# ── Tab 2: Upload
with tab2:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Upload SAS File")
        uploaded_file = st.file_uploader(
            "Choose a .sas file",
            type=["sas"],
            key="sas_uploader"
        )

        if uploaded_file:
            file_content = uploaded_file.read().decode("utf-8")
            st.code(file_content, language="sas")

            upload_col1, upload_col2 = st.columns(2)
            with upload_col1:
                ingest_btn = st.button(
                    "📥 Add to Knowledge Base",
                    use_container_width=True
                )
            with upload_col2:
                translate_upload_btn = st.button(
                    f"⟶ Translate to {target_lang}",
                    use_container_width=True,
                    key="translate_upload"
                )

            if ingest_btn:
                with st.spinner("Ingesting into ChromaDB..."):
                    count = ingest_sas_file(
                        file_content,
                        uploaded_file.name
                    )
                    st.success(f"Added {count} chunks from {uploaded_file.name} to knowledge base!")

            if translate_upload_btn:
                with st.spinner(f"Translating to {target_lang}..."):
                    try:
                        result = translate_sas(file_content, target_lang)
                        with col2:
                            st.markdown(f"#### {target_lang} Output")
                            if result["tfl_warning"]:
                                st.markdown(
                                    f'<div class="warning-box">⚠️ TFL detected: '
                                    f'{", ".join(result["tfl_warning"])}</div>',
                                    unsafe_allow_html=True
                                )
                            lang_display = "python" if target_lang == "Python" else "r"
                            st.code(result["code"], language=lang_display)
                            if result["notes"]:
                                st.markdown("**📝 Translation Notes:**")
                                for note in result["notes"]:
                                    st.markdown(f"- {note}")
                            scores = result["similarity_scores"]
                            st.markdown("**🎯 RAG Similarity Scores:**")
                            score_cols = st.columns(len(scores))
                            for i, (c, score) in enumerate(zip(score_cols, scores)):
                                c.metric(f"Match {i+1}", f"{score:.3f}")
                            with st.expander("🔍 Retrieved SAS Context"):
                                st.text(result["context"])
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
