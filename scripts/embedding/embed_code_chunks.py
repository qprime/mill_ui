#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from chromadb import PersistentClient

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from scripts.embedding.embed_cli_logs import get_embedding_function


CHUNK_DIR = ROOT_DIR / "memory/development/code_chunks"
CHROMA_PATH = ROOT_DIR / "memory/development/chroma"

def load_chunks() -> list[dict]:
    chunks = []
    for json_file in CHUNK_DIR.rglob("*.json"):
        rel_path = json_file.relative_to(CHUNK_DIR)
        with open(json_file, "r", encoding="utf-8") as f:
            file_chunks = json.load(f)
            for i, chunk in enumerate(file_chunks):
                name = chunk.get("name", f"anon_{i}")
                chunk_id = f"{rel_path.with_suffix('').as_posix()}::{name}_{i}"
                chunks.append({
                    "id": chunk_id,
                    "text": chunk["code"],
                    "metadata": {
                        "file": str(json_file.relative_to(ROOT_DIR)),
                        "name": name,
                        "type": chunk.get("type"),
                        "start_line": chunk.get("start_line"),
                        "end_line": chunk.get("end_line"),
                        "docstring": chunk.get("docstring", "")
                    }
                })
    return chunks




def embed_chunks():
    ef = get_embedding_function()
    client = PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(name="code_chunks", embedding_function=ef)

    print(f"📥 Loading chunks from: {CHUNK_DIR}")
    chunks = load_chunks()

    if not chunks:
        print("⚠️ No chunks found.")
        return

    ids = [c["id"] for c in chunks]
    docs = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    print(f"🔄 Embedding {len(chunks)} code chunks into ChromaDB...")

    # Clear previous entries
    existing = collection.get()
    existing_ids = existing.get("ids", []) if existing else []
    if existing_ids:
        collection.delete(ids=existing_ids)

    collection.add(documents=docs, ids=ids, metadatas=metadatas)
    print(f"✅ Embedded {len(chunks)} chunks into 'code_chunks' collection.")

if __name__ == "__main__":
    embed_chunks()
