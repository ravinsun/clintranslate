import json
import os
import re
import requests
import tempfile
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# ── 1. Load embedding model ──────────────────────────────────────────
print("Loading HuggingFace embedding model...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# ── 2. Init ChromaDB ─────────────────────────────────────────────────
chroma_client = chromadb.PersistentClient(path="./chroma_store_v2")
collection = chroma_client.get_or_create_collection(
    name="sas_only_corpus",
    metadata={"hnsw:space": "cosine"}
)

# ── 3. TFL Detector ──────────────────────────────────────────────────
TFL_PROCS = [
    "PROC REPORT", "PROC TABULATE", "ODS RTF",
    "ODS PDF", "ODS HTML", "PROC GPLOT",
    "PROC SGPLOT", "PROC SGPANEL"
]

def detect_tfl(sas_code: str):
    flags = [p for p in TFL_PROCS if p.upper() in sas_code.upper()]
    return flags if flags else None

# ── 4. Ingest SAS-only knowledge base ────────────────────────────────
def ingest_sas_examples(json_path="data/sas_examples.json"):
    with open(json_path, "r") as f:
        examples = json.load(f)

    existing_ids = set(collection.get()["ids"])
    new_docs, new_embeddings, new_ids, new_metas = [], [], [], []

    for ex in examples:
        if ex["id"] not in existing_ids:
            # Embed SAS code + description only (no Python)
            text = f"SAS: {ex['sas']} | Description: {ex['description']} | Domain: {ex['domain']}"
            embedding = embedder.encode(text).tolist()
            new_docs.append(text)
            new_embeddings.append(embedding)
            new_ids.append(ex["id"])
            new_metas.append({
                "sas": ex["sas"],
                "description": ex["description"],
                "domain": ex["domain"],
                "proc_type": ex["proc_type"]
            })

    if new_docs:
        collection.add(
            documents=new_docs,
            embeddings=new_embeddings,
            ids=new_ids,
            metadatas=new_metas
        )
        print(f"Ingested {len(new_docs)} SAS examples into ChromaDB.")
    else:
        print("ChromaDB already up to date.")

# ── 5. Ingest from uploaded .sas file ────────────────────────────────
def ingest_sas_file(file_content: str, file_name: str):
    chunks = chunk_sas_code(file_content)
    existing_ids = set(collection.get()["ids"])
    new_docs, new_embeddings, new_ids, new_metas = [], [], [], []

    for i, chunk in enumerate(chunks):
        chunk_id = f"upload_{file_name}_{i}"
        if chunk_id not in existing_ids:
            text = f"SAS: {chunk} | Source: {file_name}"
            embedding = embedder.encode(text).tolist()
            new_docs.append(text)
            new_embeddings.append(embedding)
            new_ids.append(chunk_id)
            new_metas.append({
                "sas": chunk,
                "description": f"Uploaded from {file_name}",
                "domain": "Uploaded",
                "proc_type": detect_proc_type(chunk)
            })

    if new_docs:
        collection.add(
            documents=new_docs,
            embeddings=new_embeddings,
            ids=new_ids,
            metadatas=new_metas
        )
        return len(new_docs)
    return 0

# ── 6. Ingest from GitHub repo URL ───────────────────────────────────
def ingest_github_repo(github_url: str):
    # Convert GitHub URL to API format
    # e.g. https://github.com/user/repo → api.github.com/repos/user/repo
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)", github_url)
    if not match:
        return 0, "Invalid GitHub URL format"

    owner, repo = match.group(1), match.group(2).rstrip("/")
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"

    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200:
            # Try master branch
            api_url = api_url.replace("/main?", "/master?")
            response = requests.get(api_url, timeout=10)

        tree = response.json().get("tree", [])
        sas_files = [f for f in tree if f["path"].endswith(".sas")]

        if not sas_files:
            return 0, "No .sas files found in repository"

        ingested = 0
        for sas_file in sas_files[:20]:  # Limit to 20 files
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{sas_file['path']}"
            file_response = requests.get(raw_url, timeout=10)
            if file_response.status_code == 200:
                count = ingest_sas_file(
                    file_response.text,
                    sas_file["path"]
                )
                ingested += count

        return ingested, f"Successfully ingested {ingested} chunks from {len(sas_files)} SAS files"

    except Exception as e:
        return 0, f"Error: {str(e)}"

# ── 7. Smart SAS chunker ─────────────────────────────────────────────
def chunk_sas_code(content: str):
    # Resolve %INCLUDE references (flag them)
    content = re.sub(
        r'%INCLUDE\s+["\'](.+?)["\'];?',
        r'/* %INCLUDE: \1 */',
        content,
        flags=re.IGNORECASE
    )

    # Split on PROC/DATA/MACRO boundaries
    pattern = re.compile(
        r'(?=PROC\s+\w+|DATA\s+\w+|%MACRO\s+\w+)',
        re.IGNORECASE
    )
    raw_chunks = pattern.split(content)
    chunks = []

    for chunk in raw_chunks:
        chunk = chunk.strip()
        if len(chunk) > 30:  # Skip empty/tiny chunks
            chunks.append(chunk)

    return chunks if chunks else [content]

def detect_proc_type(sas_code: str):
    procs = ["PROC SORT", "PROC MEANS", "PROC FREQ", "PROC REPORT",
             "PROC TRANSPOSE", "PROC MIXED", "PROC LIFETEST",
             "DATA step", "%MACRO"]
    for proc in procs:
        if proc.upper() in sas_code.upper():
            return proc
    return "Unknown"

# ── 8. Retrieve similar SAS context ──────────────────────────────────
def retrieve_context(sas_query: str, k: int = 3):
    query_embedding = embedder.encode(sas_query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )

    context_parts = []
    scores = []

    for i, (meta, distance) in enumerate(zip(
        results["metadatas"][0],
        results["distances"][0]
    )):
        # Convert distance to similarity score
        similarity = round(1 - distance, 3)
        scores.append(similarity)
        context_parts.append(
            f"Example {i+1} (similarity: {similarity}):\n"
            f"  SAS:         {meta['sas']}\n"
            f"  Description: {meta['description']}\n"
            f"  Domain:      {meta['domain']}\n"
            f"  Type:        {meta['proc_type']}"
        )

    return "\n\n".join(context_parts), scores

# ── 9. Translate SAS → Python or R ───────────────────────────────────
def translate_sas(sas_code: str, target_lang: str = "Python") -> dict:
    client = Anthropic()
    tfl_warning = detect_tfl(sas_code)
    context, scores = retrieve_context(sas_code)

    if target_lang == "Python":
        lang_instructions = """Translate to Python using pandas and numpy.
Use idiomatic pandas — avoid loops, use vectorized operations.
Preserve all clinical variable names (USUBJID, PARAMCD, AVAL, TRTA etc.) exactly."""
        code_lang = "python"
        example_libs = "import pandas as pd\nimport numpy as np"

    else:  # R
        lang_instructions = """Translate to R using tidyverse and Pharmaverse packages.
Use dplyr, tidyr, and admiral where appropriate.
For survival analysis use the survival package.
For mixed models use nlme or lme4.
Preserve all clinical variable names exactly."""
        code_lang = "r"
        example_libs = "library(dplyr)\nlibrary(tidyr)\nlibrary(admiral)"

    system_prompt = f"""You are an expert clinical data engineer specializing in 
pharmaceutical SDTM and ADaM programming.
{lang_instructions}
Add inline comments explaining key translation decisions.
After the code block provide 3-5 Translation Notes as bullet points."""

    user_prompt = f"""Here are similar SAS programs from the knowledge base for structural context:

{context}

Now translate this SAS code to {target_lang} from scratch.
Generate the {target_lang} code yourself based on your expertise.
Do NOT copy code from the examples above — use them for domain context only.

SAS code to translate:
{sas_code}

Format your response as:
```{code_lang}
{example_libs}
# Your translation here
```

**Translation Notes:**
- note 1
- note 2"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    raw = response.content[0].text

    # Parse code block
    code_match = re.search(
        rf"```{code_lang}\n([\s\S]*?)```", raw
    )
    code = code_match.group(1).strip() if code_match else raw

    # Parse notes
    notes_match = re.search(
        r"\*\*Translation Notes:\*\*([\s\S]*?)$", raw
    )
    notes_raw = notes_match.group(1).strip() if notes_match else ""
    notes = [
        l.replace("- ", "").strip()
        for l in notes_raw.split("\n")
        if l.strip().startswith("-")
    ]

    return {
        "code": code,
        "notes": notes,
        "context": context,
        "similarity_scores": scores,
        "tfl_warning": tfl_warning,
        "target_lang": target_lang
    }

# ── Run ingestion on import ───────────────────────────────────────────
ingest_sas_examples()
