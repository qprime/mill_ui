import chromadb
import requests

CHROMA_PATH = "../memory/lab"
COLLECTION_NAME = "lab_devices"
LLM_URL = "http://localhost:11434/generate"

# Connect to Chroma
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(name=COLLECTION_NAME)

# Ask user for a query
query = input("🔍 What do you want to know about your devices? ")

# Search the vector DB
results = collection.query(query_texts=[query], n_results=5)
docs = results["documents"][0]

# Show raw matches first
print("\n🔎 Top matching devices:\n")
for i, doc in enumerate(docs):
    print(f"--- Device {i+1} ---\n{doc.strip()}\n")

# Optional: summarize with LLM
use_llm = input("🧠 Summarize with Mistral? (y/n): ").lower() == "y"

if use_llm:
    context = "\n".join([f"{doc.strip()}" for doc in docs])
    prompt = f"""You are a device inventory assistant.

The user asked: "{query}"

Here is a summary of the top matching devices:
{context}

Based on this, answer the user's question."""
    
    try:
        res = requests.post(LLM_URL, json={"prompt": prompt, "max_tokens": 300})
        res.raise_for_status()
        print("\n🧠 LLM Response:\n" + res.json()["response"].strip())
    except Exception as e:
        print("❌ Error calling LLM:", e)
