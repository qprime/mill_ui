from chromadb import PersistentClient

from pathlib import Path
from typing import List

ROOT_DIR = Path(__file__).resolve().parents[2]
CHROMA_PATH = ROOT_DIR / "memory/development/chroma"

from scripts.embedding.embed_cli_logs import get_embedding_function

CONTEXT_SOURCES = {
    "project_docs": 100,
    "code_chunks": 1000,
    # Future: "tasks": 2, "cli_logs": 2
}

def get_combined_context(prompt: str, max_total: int = 10) -> str:
    client = PersistentClient(path=str(CHROMA_PATH))
    embedding_fn = get_embedding_function()
    context_blocks: List[str] = []
    total_loaded = 0

    for collection_name, per_collection_limit in CONTEXT_SOURCES.items():
        try:
            collection = client.get_collection(name=collection_name, embedding_function=embedding_fn)
            results = collection.query(query_texts=[prompt], n_results=per_collection_limit)
            documents = results.get("documents", [[]])[0]

            if documents:
                tagged = "\n\n".join(documents)
                block = f"# From {collection_name}:\n{tagged}"
                context_blocks.append(block)
                total_loaded += len(documents)

            # if total_loaded >= max_total:
            #     break

        except Exception as e:
            print(f"⚠️ Context query failed for '{collection_name}': {e}")

    return "\n\n".join(context_blocks) if context_blocks else "[No relevant project context found.]"