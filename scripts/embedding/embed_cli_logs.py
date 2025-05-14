import os
import json
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# --- Setup embedding function ---
openai_ef = OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),  # Set this in your shell or .bashrc
    model_name="text-embedding-3-small"
)

# --- Connect to Chroma ---
chroma_client = chromadb.PersistentClient(path="../memory/cliff_state")

# --- Rebuild the collection if needed ---
if "cli_logs" in [c.name for c in chroma_client.list_collections()]:
    chroma_client.delete_collection("cli_logs")

collection = chroma_client.get_or_create_collection(
    name="cli_logs",
    embedding_function=openai_ef
)

# --- Load CLI logs ---
cli_log_path = Path("../memory/cliff_state/cli_logs.jsonl")
if not cli_log_path.exists():
    print("❌ CLI log file not found.")
    exit(1)

with cli_log_path.open("r", encoding="utf-8") as f:
    lines = [json.loads(line) for line in f.readlines()]

# --- Prepare batch documents ---
documents = []
metadatas = []
ids = []

for idx, log in enumerate(lines):
    text = f"{log['timestamp']} {log['hostname']} {log['command']}"
    documents.append(text)
    metadatas.append({
        "source": "cli_logs",
        "hostname": log["hostname"],
        "session_id": log["session_id"]
    })
    ids.append(f"cli-{idx}")

# --- Embed and persist ---
collection.add(
    documents=documents,
    ids=ids,
    metadatas=metadatas
)

chroma_client.persist()
print(f"✅ Embedded {len(documents)} CLI commands into cliff_state memory.")

