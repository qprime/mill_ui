import sys
import os
import json
from pathlib import Path
from chromadb import PersistentClient
from scripts.embedding.embed_cli_logs import get_embedding_function

# --- Setup root and import paths ---
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

# --- Embedding wrapper ---
def EmbedFunction():
    return get_embedding_function()

# --- Main loader ---
def load_summaries():
    summary_dir = ROOT_DIR / "memory/development/module_summaries"
    chroma_path = ROOT_DIR / "memory/development/chroma"

    client = PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name="project_docs",
        embedding_function=EmbedFunction()
    )

    docs = []
    ids = []

    for file in summary_dir.glob("*.md"):
        text = file.read_text().strip()
        if text:
            docs.append(text)
            ids.append(file.stem)

    if docs:
        print(f"📚 Loading {len(docs)} summaries into ChromaDB...")
        existing = collection.get()
        ids_to_delete = existing.get("ids", []) if existing else []
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
        collection.add(documents=docs, ids=ids)
        print("✅ Summaries loaded.")
    else:
        print("⚠️ No summaries found.")

if __name__ == "__main__":
    load_summaries()
