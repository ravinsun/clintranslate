# 🧬 ClinTranslate — SAS → Python Translator

> RAG-powered clinical data code translation using HuggingFace,
> ChromaDB, Anthropic Claude, and Streamlit.

Built as a proof-of-concept for AI-assisted SAS→Python migration
in pharmaceutical SDTM/ADaM pipelines.

---
## 🏗️ Architecture

```text
SAS Input
    ↓
HuggingFace Embeddings (all-MiniLM-L6-v2)
    ↓
ChromaDB Vector Store (cosine similarity)
    ↓
Claude API (RAG context + translation)
    ↓
Python Output + Translation Notes
```
---

## 📦 Stack

| Component | Technology |
|---|---|
| Embedding Model | HuggingFace all-MiniLM-L6-v2 |
| Vector Store | ChromaDB (persistent, cosine) |
| LLM | Anthropic Claude |
| UI | Streamlit |
| Language | Python 3.x |

---

## 🚀 Quick Start

**1. Clone the repo**
```bash
git clone https://github.com/YOUR_USERNAME/clintranslate.git
cd clintranslate
```

**2. Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install chromadb sentence-transformers anthropic streamlit python-dotenv
```

**4. Add your API key**
```bash
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

**5. Ingest knowledge base**
```bash
python rag_engine.py
```

**6. Launch app**
```bash
streamlit run app.py
```

Open http://localhost:8501

---

## 📁 Project Structure

clintranslate/
├── data/
│   └── examples.json      ← 8 SAS→Python clinical pairs
├── rag_engine.py          ← RAG core: embed, retrieve, translate
├── app.py                 ← Streamlit UI
├── requirements.txt       ← Dependencies
└── .env                   ← API key (not committed)

---

## 🧪 What Translates Well

| SAS Operation | Python Equivalent | Fidelity |
|---|---|---|
| PROC SORT | sort_values() | ✅ High |
| PROC MEANS | groupby + agg | ✅ High |
| DATA step MERGE | pd.merge | ✅ High |
| Change from baseline | groupby transform | ✅ High |
| PROC FREQ | pd.crosstab | ✅ High |
| PROC REPORT / ODS RTF | ⚠️ Manual review | ❌ Limited |

---

## 🗺️ Roadmap

- [ ] SAS → R translation (tidyverse / admiral)
- [ ] GitHub webhook ingestion pipeline
- [ ] %INCLUDE resolver and dependency graph
- [ ] Validation tab (XPT diff testing)
- [ ] TFL detector (flag PROC REPORT for manual review)
- [ ] Docker container for team deployment

---

## 👤 Author

**Ravinder Maramamula**
Senior Data Engineer | Redbock / BioMarin
[[LinkedIn](https://www.linkedin.com/in/ravindermaramamula/)

---

## ⚠️ Disclaimer

This tool is a proof-of-concept. Translated code requires 
full IQ/OQ/PQ validation before use in any GxP or 
submission context.

## 🚀 Version History

### v2 — SAS-only RAG Corpus (Current)
- Knowledge base contains SAS programs only — no hand-written Python
- Claude generates Python OR R from scratch using domain context
- Language selector — Python (pandas) or R (tidyverse/admiral)
- File upload support — translate any .sas file directly
- GitHub repo ingestion — connect any SAS repository
- TFL detector — flags PROC REPORT/ODS for manual review
- Cosine similarity scores visible for every translation

### v1 — SAS+Python Pairs (Original)
- RAG with hand-written SAS→Python translation pairs
- Python output only
- 8 clinical examples as knowledge base

## 🗺️ Roadmap

- [x] v1: SAS+Python RAG pairs
- [x] v2: SAS-only corpus, Python+R output, GitHub ingestion
- [ ] v3: Org coding standards as knowledge base
- [ ] %INCLUDE resolver with dependency graph
- [ ] Validation tab — XPT diff testing
- [ ] Docker container for team deployment
- [ ] Fine-tuned clinical embedding model
