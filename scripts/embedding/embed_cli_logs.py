import os
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

def get_embedding_function():
    api_key = os.getenv("OPENAI_API_KEY")
    model_name = "text-embedding-3-small"
    return OpenAIEmbeddingFunction(api_key=api_key, model_name=model_name)

# Optional: keep embedding logic for CLI use
if __name__ == "__main__":
    import json
    from pathlib import Path
    import chromadb

    chroma_client = chromadb.PersistentClient(path="memory/cliff_state")
    cli_log_path = Path("memory/cliff_state/cli_logs.jsonl")

    if not cli_log_path.exists():
        print("❌ CLI log file not found.")
        exit(1)

    with cli_log_path.open("r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

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

    collection = chroma_client.get_or_create_collection(
        name="cli_logs",
        embedding_function=get_embedding_function()
    )
    collection.delete(where={})  # Optional: clear old data
    collection.add(documents=documents, ids=ids, metadatas=metadatas)
    chroma_client.persist()
    print(f"✅ Embedded {len(documents)} CLI commands into cliff_state memory.")
