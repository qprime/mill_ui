"""ai_router.py

Unified LLM and embedding router for CLIFF AI.
Provides a central interface for chat and embedding requests.
All provider logic (OpenAI, Phi, etc.) is routed through client.py.
"""

from cliff_ai.scripts.llm.client import get_chat_completion, get_embedding

class AIRouter:
    def embed(self, inputs: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
        return get_embedding(inputs, model=model)

    def chat(self, messages: list[dict], model: str = "gpt-4.1-mini") -> str:
        return get_chat_completion(messages, model=model)

def get_router(source: str = "openai") -> AIRouter:
    if source == "openai":
        return AIRouter()
    else:
        raise ValueError(f"Unknown AI source: {source}")
