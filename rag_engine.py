import json
import os
import chromadb
from sentence_transformers import SentenceTransformer
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# ── 1. Load embedding model ──────────────────────────────────────────
print("Loading HuggingFace embedding model...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# ── 2. Init ChromaDB (local persistent store) ────────────────────────
chroma_client = chromadb.PersistentClient(path="./chroma_store")

collection = chroma_client.get_or_create_collection(
    name="sas_python_pairs",
    metadata={"hnsw:space": "cosine"}
)

# ── 3. Ingest examples.json into ChromaDB ───────────────────────────
def ingest_examples():
    with open("data/examples.json", "r") as f:
        examples = json.load(f)

    existing = collection.get()
    existing_ids = set(existing["ids"])

    new_docs, new_embeddings, new_ids, new_metas = [], [], [], []

    for ex in examples:
        if ex["id"] not in existing_ids:
            text = f"SAS: {ex['sas']} | Description: {ex['description']}"
            embedding = embedder.encode(text).tolist()
            new_docs.append(text)
            new_embeddings.append(embedding)
            new_ids.append(ex["id"])
            new_metas.append({"sas": ex["sas"], "python": ex["python"], "description": ex["description"]})

    if new_docs:
        collection.add(documents=new_docs, embeddings=new_embeddings, ids=new_ids, metadatas=new_metas)
        print(f"Ingested {len(new_docs)} examples into ChromaDB.")
    else:
        print("ChromaDB already up to date.")

# ── 4. Retrieve top-k similar SAS→Python pairs ───────────────────────
def retrieve_context(sas_query: str, k: int = 3) -> str:
    query_embedding = embedder.encode(sas_query).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=k)

    context_parts = []
    for i, meta in enumerate(results["metadatas"][0]):
        context_parts.append(
            f"Example {i+1}:\n"
            f"  SAS:    {meta['sas']}\n"
            f"  Python: {meta['python']}\n"
            f"  Note:   {meta['description']}"
        )
    return "\n\n".join(context_parts)

# ── 5. Translate using Claude + retrieved context ────────────────────
def translate_sas_to_python(sas_code: str) -> dict:
    client = Anthropic()
    context = retrieve_context(sas_code)

    system_prompt = """You are an expert clinical data engineer specializing in 
translating SAS code to Python (pandas/numpy) for pharma SDTM/ADaM pipelines.
Use the retrieved examples as reference patterns. Preserve all clinical variable 
names exactly. Add inline comments. After the code, provide 3-5 Translation Notes 
as bullet points explaining key differences."""

    user_prompt = f"""Here are similar SAS→Python translation examples for reference:

{context}

Now translate this SAS code to Python:

{sas_code}

Format your response as:
```python
# code here
```

**Translation Notes:**
- note 1
- note 2"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    raw = response.content[0].text

    # Parse code block
    import re
    code_match = re.search(r"```python\n([\s\S]*?)```", raw)
    code = code_match.group(1).strip() if code_match else raw

    # Parse notes
    notes_match = re.search(r"\*\*Translation Notes:\*\*([\s\S]*?)$", raw)
    notes_raw = notes_match.group(1).strip() if notes_match else ""
    notes = [l.replace("- ", "").strip() for l in notes_raw.split("\n") if l.strip().startswith("-")]

    return {"python_code": code, "notes": notes, "context_used": context}


# ── 6. Run ingestion on import ───────────────────────────────────────
ingest_examples()
