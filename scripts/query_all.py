import chromadb
import requests

CHROMA_PATH = "../memory/lab"
COLLECTION_NAME = "lab_devices"
LLM_URL = "http://localhost:11434/generate"

# Connect to Chroma
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(name=COLLECTION_NAME)

# Pull ALL entries (with hacky workaround for Chroma's n_results cap)
results = collection.get()
docs = results["documents"]
all_docs = [doc.strip() for doc in docs]

print(f"\n📦 Retrieved {len(all_docs)} total documents from '{COLLECTION_NAME}' collection.\n")

for i, doc in enumerate(all_docs):
    print(f"--- Entry {i+1} ---\n{doc}\n")

# Optional: summarize
summarize = input("🧠 Summarize all results using Mistral? (y/n): ").lower() == "y"

if summarize:
    prompt = f"""You are an inventory assistant.

The user wants a summary of all tracked lab devices.

Here is the full device data:

{chr(10).join(all_docs)}

Summarize the devices, their roles, and any noteworthy patterns."""
    
    try:
        res = requests.post(LLM_URL, json={"prompt": prompt, "max_tokens": 500})
        res.raise_for_status()
        print("\n🧠 LLM Summary:\n" + res.json()["response"].strip())
    except Exception as e:
        print("❌ LLM Error:", e)

