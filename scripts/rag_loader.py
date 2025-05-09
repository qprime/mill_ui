# rag_loader.py (patched to force clean collection with correct embedding function)
import os
from pathlib import Path
from openai import OpenAI
import tiktoken
from chromadb import PersistentClient
from chromadb.config import Settings

SUMMARY_DIR = Path("memory/development/module_summaries")
COLLECTION_NAME = "project_docs"

# Manual embedding wrapper that matches Chroma's required interface

class ManualOpenAIEmbedder:
    def __init__(self, model="text-embedding-3-small"):
        self.model = model
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def __call__(self, input: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.model,
            input=input
        )
        return [d.embedding for d in response.data]

def count_tokens(text, model="text-embedding-3-small"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def load_summaries():
    print("📥 Loading module summaries into ChromaDB...")
    #client = Client(Settings(persist_directory="chroma_store"))

    client = PersistentClient(path="chroma_store")

    # Force delete and recreate collection with proper embedding function
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"🧹 Cleared existing collection: {COLLECTION_NAME}")
    except:
        print(f"ℹ️ No existing collection to delete.")

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=ManualOpenAIEmbedder()
    )

    for summary_file in SUMMARY_DIR.glob("*.md"):
        doc_id = summary_file.stem
        with open(summary_file, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            continue

        try:
            tokens = count_tokens(content)

            collection.upsert(
                documents=[content],
                ids=[doc_id],
                metadatas=[{"source": str(summary_file), "tokens": tokens}]
            )
            print(f"✅ Embedded: {doc_id} ({tokens} tokens)")
        except Exception as e:
            print(f"❌ Failed to embed {doc_id}: {e}")

def query_project_docs(question: str, n_results=3):
    print(f"\n🔍 Query: {question}\n")
    client = PersistentClient(path="chroma_store")

    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=ManualOpenAIEmbedder()  # ← ensure same embedder
    )

    results = collection.query(query_texts=[question], n_results=n_results)
    for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
        print(f"From {meta['source']}\n---\n{doc}\n---\n")

if __name__ == "__main__":
    import sys
    load_summaries()
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        query_project_docs(query)
    else:
        print("✨ Summaries loaded. Run with a query like: python rag_loader.py 'what does lab_manager do?'")
