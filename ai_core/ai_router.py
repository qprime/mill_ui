# path: ai_core/ai_router.py
# type: routing module
# tags: ai, routing, embeddings, chat
# owner: cliff
# depends_on: ai_core/client.py
# description: Provides routing for AI functionalities including embeddings and chat completions.

from ai_core.client import get_chat_completion, get_embedding


class AIRouter:
    def embed(
        self, inputs: list[str], model: str = "text-embedding-3-small"
    ) -> list[list[float]]:
        return get_embedding(inputs, model=model)

    def chat(self, messages: list[dict], model: str = "gpt-4.1-mini") -> str:
        return get_chat_completion(messages, model=model)


def get_router(source: str = "openai") -> AIRouter:
    if source == "openai":
        return AIRouter()
    else:
        raise ValueError(f"Unknown AI source: {source }")
