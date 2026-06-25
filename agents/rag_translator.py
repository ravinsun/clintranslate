"""
Agent 2: RAG Translator
For each SAS file in execution order:
  1. Embed the SAS code with HuggingFace
  2. Retrieve top-3 similar examples from ChromaDB
  3. Call Claude to translate with retrieved context
  4. Return Python output + cosine similarity score
"""

import os
import time
from pathlib import Path
from typing import TypedDict, List, Dict, Any
import chromadb
import anthropic

# Lazy imports — only loaded when agent runs
_chroma_client = None
_embedding_fn = None
_collection = None


def _init_rag():
    """Initialize ChromaDB + HuggingFace embedding (lazy, once per session)."""
    global _chroma_client, _embedding_fn, _collection

    if _collection is not None:
        return

    from sentence_transformers import SentenceTransformer

    embed_model = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
    chroma_path = os.getenv("CHROMA_PATH", "./chroma_store_v3")
    collection_name = os.getenv("CHROMA_COLLECTION", "coding_standards")

    _embedding_fn = SentenceTransformer(embed_model)
    _chroma_client = chromadb.PersistentClient(path=chroma_path)
    # Load collection WITHOUT embedding function — we embed manually
    _collection = _chroma_client.get_collection(name=collection_name)


def retrieve_context(sas_code: str, n_results: int = 3) -> tuple[str, float]:
    """
    Retrieve top-n similar SAS examples from ChromaDB.
    Embeds the query manually using SentenceTransformer.
    """
    _init_rag()

    # Embed the query manually
    query_embedding = _embedding_fn.encode(sas_code).tolist()

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, _collection.count() or 1),
        include=["documents", "metadatas", "distances"],
    )

    if not results["documents"] or not results["documents"][0]:
        return "No similar examples found in knowledge base.", 0.0

    context_parts = []
    distances = results["distances"][0]
    best_score = round(1 - min(distances), 4)

    for i, (doc, meta) in enumerate(
        zip(results["documents"][0], results["metadatas"][0])
    ):
        source = meta.get("source", f"example_{i+1}")
        context_parts.append(f"--- Example {i+1} [{source}] ---\n{doc}")

    return "\n\n".join(context_parts), best_score


def translate_with_claude(sas_code: str, context: str, filename: str) -> str:
    """
    Call Claude API with RAG context to translate SAS → Python.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    system_prompt = """You are a senior clinical data engineer specializing in SAS-to-Python 
translation for CDISC SDTM and ADaM pipelines in GxP pharmaceutical environments.

Your translations must:
1. Use pandas/numpy idioms that mirror SAS intent exactly
2. Preserve variable names, label logic, and dataset structure
3. Add inline comments mapping SAS constructs to Python equivalents
4. Flag PROC REPORT / ODS RTF blocks with # [REQUIRES_MANUAL_REVIEW: TFL output]
5. Follow 21 CFR Part 11 awareness: no silent data modification

Output ONLY the translated Python code with comments. No preamble.
Never end a line with % or other non-Python characters.
Always close all parentheses, brackets, and braces before ending a statement.
Never wrap output in markdown code fences."""

    user_prompt = f"""Translate this SAS program to Python.

File: {filename}

--- Retrieved Context (similar clinical examples) ---
{context}

--- SAS Program to Translate ---
{sas_code}

Translate the above SAS to clean, production-ready Python using pandas/numpy.
Add a comment block at the top: # Translated from: {filename} | ClinTranslate v4 Agentic"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text
    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    # Fix stray % artifacts (Claude line-continuation bug)
    import re
    raw = re.sub(r'%\s*\n\s*\(', '(', raw)
    raw = re.sub(r'%\s*$', '', raw, flags=re.MULTILINE)
    return raw.strip()


class TranslatorState(TypedDict):
    sas_files: List[str]
    translations: Dict[str, Dict[str, Any]]  # filename -> {python_code, score, time_sec}
    translator_notes: List[str]


def run_rag_translator(state: TranslatorState) -> TranslatorState:
    """
    LangGraph node: Translates each SAS file using RAG + Claude.
    """
    translations = {}
    notes = []

    for filepath in state["sas_files"]:
        filename = Path(filepath).name
        start = time.time()

        try:
            with open(filepath, "r", errors="ignore") as f:
                sas_code = f.read()

            sas_loc = len([l for l in sas_code.splitlines() if l.strip()])
            context, score = retrieve_context(sas_code)
            python_code = translate_with_claude(sas_code, context, filename)
            py_loc = len([l for l in python_code.splitlines() if l.strip()])
            elapsed = round(time.time() - start, 1)

            translations[filename] = {
                "python_code": python_code,
                "cosine_score": score,
                "sas_loc": sas_loc,
                "py_loc": py_loc,
                "translation_time_sec": elapsed,
                "status": "translated",
                "error": None,
            }
            notes.append(f"✅ {filename} → score={score}, {elapsed}s")

        except Exception as e:
            elapsed = round(time.time() - start, 1)
            translations[filename] = {
                "python_code": "",
                "cosine_score": 0.0,
                "sas_loc": 0,
                "py_loc": 0,
                "translation_time_sec": elapsed,
                "status": "error",
                "error": str(e),
            }
            notes.append(f"❌ {filename} → error: {e}")

    state["translations"] = translations
    state["translator_notes"] = notes
    return state
