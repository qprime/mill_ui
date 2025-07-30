"""ai_router.py

Unified LLM and embedding router for CLIFF AI.
Provides a central interface for chat and embedding requests.
All provider logic (OpenAI, Phi, etc.) is routed through client.py.
"""

from scripts.llm.client import get_chat_completion, get_embedding

class AIRouter:
    """Central router for AI chat and embedding requests."""

    def embed(self, inputs: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
        return get_embedding(inputs, model=model)

    def chat(self, messages: list[dict], model: str = "gpt-4.1-mini") -> str:
        return get_chat_completion(messages, model=model)

def get_router(source: str = "openai") -> AIRouter:
    """
    Returns a configured AIRouter.
    For now, only 'openai' is supported, but this is future-proofed for multi-backend.
    """
    if source == "openai":
        return AIRouter()
    else:
        raise ValueError(f"Unknown AI source: {source}")

# Optional: Test code for direct CLI/test usage
if __name__ == "__main__":
    # Minimal smoke test for router functionality
    router = get_router()
    msg = [{"role": "user", "content": "Say hello as CLIFF."}]
    print("[Test] Chat:", router.chat(msg))
    print("[Test] Embedding:", router.embed(["hello world"]))
