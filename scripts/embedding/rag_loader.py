# rag_loader.py (patched to use callable wrapper for Chroma embedding interface)
import os
from pathlib import Path
import tiktoken
from chromadb import PersistentClient
from scripts.utils.ai_router import get_router

SUMMARY_DIR = Path(__file__).resolve().parent.parent / "memory" / "development" / "module_summaries"

COLLECTION_NAME = "project_docs"

class EmbedFunction:
    def __call__(self, input: list[str]) -> list[list[float]]:
        return get_router("openai").embed(input)

def count_tokens(text, model="text-embedding-3-small"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def load_summaries():
    print("📥 Loading module summaries into ChromaDB...")
    print("📁 Using Chroma DB path:", Path("chroma_store").resolve())

    client = PersistentClient(path=str(Path(__file__).resolve().parent.parent / "chroma_store"))


    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"🧹 Cleared existing collection: {COLLECTION_NAME}")
    except:
        print(f"ℹ️ No existing collection to delete.")

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=EmbedFunction()
    )
    print(f"📄 Scanning: {SUMMARY_DIR}")

    for summary_file in SUMMARY_DIR.glob("*.md"):
        doc_id = summary_file.stem
        with open(summary_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            print(f"📦 Embedding {doc_id} from {summary_file}")


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
    client = PersistentClient(path=str(Path(__file__).resolve().parent.parent / "chroma_store"))


    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=EmbedFunction()
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
