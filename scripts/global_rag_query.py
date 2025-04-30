from chromadb import PersistentClient
from llm_router import ask_llm

CHROMA_PATHS = {
    "lab_devices": "../memory/lab",
    "cli_logs": "../memory/cliff_state",
    # Add more collections and paths here
}

QUERY = input("🔎 Ask Cliff: ")

# Aggregate top results across domains
chunks = []

for name, path in CHROMA_PATHS.items():
    try:
        client = PersistentClient(path=path)
        collection = client.get_collection(name=name)
        result = collection.query(query_texts=[QUERY], n_results=5)

        docs = result["documents"][0]
        if docs:
            header = f"\n--- {name.replace('_', ' ').title()} ---\n"
            chunks.append(header + "\n".join(doc.strip() for doc in docs))

    except Exception as e:
        print(f"⚠️ Failed to query {name}: {e}")

# Combine all results into one context block
context = "\n".join(chunks)

if not context:
    print("❌ No relevant memory found.")
    exit()

# Build the prompt for the LLM
prompt = f"""You are Cliff, a context-aware assistant. The user asked:

\"{QUERY}\"

Here is the most relevant memory from different sources:
{context}

Based on this, answer the user's question clearly and accurately."""

# Call the LLM
response = ask_llm(prompt, max_tokens=500)
print("\n🧠 Cliff Says:\n" + response.strip())

