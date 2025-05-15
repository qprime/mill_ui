import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[2])
sys.path.append(ROOT_DIR)

from chromadb import PersistentClient
from scripts.embedding.embed_cli_logs import get_embedding_function
from pathlib import Path
import os
import json

def EmbedFunction():
    return get_embedding_function()

def load_summaries():
    root = Path(__file__).resolve().parents[2] / "memory/development/module_summaries"
    client = PersistentClient(path="memory/development/chroma")
    collection = client.get_or_create_collection(name="project_docs", embedding_function=EmbedFunction())

    docs = []
    ids = []
    for file in root.glob("*.md"):
        text = file.read_text()
        if not text.strip():
            continue
        docs.append(text)
        ids.append(str(file.stem))

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
