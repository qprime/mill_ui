import json
import chromadb
import requests

CHROMA_PATH = "../memory/cliff_state"
LLM_URL = "http://localhost:11434/generate"
COLLECTION_NAME = "cli_logs"

# Connect to ChromaDB
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(name=COLLECTION_NAME)

# Accept user query
query = input("🔍 What do you want to know? ")

# Retrieve top matches
results = collection.query(query_texts=[query], n_results=5)
docs = results["documents"][0]

# Format context for the LLM
context = "\n".join([f"- {doc}" for doc in docs])
prompt = f"""You are a CLI command assistant.

The user asked: "{query}"

Here are past related CLI commands:
{context}

Answer with a helpful response based only on these commands.
"""

# Send to local LLM
try:
    res = requests.post(LLM_URL, json={"prompt": prompt, "max_tokens": 300})
    res.raise_for_status()
    response = res.json()["response"]
    print("\n🧠 Response:\n" + response.strip())

except Exception as e:
    print("❌ Error calling local LLM:", e)

