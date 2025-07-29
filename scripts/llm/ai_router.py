# ai_router.py
from abc import ABC, abstractmethod
import os

### === Interface Definitions === ###

class EmbeddingBackend(ABC):
    @abstractmethod
    def embed(self, inputs: list[str]) -> list[list[float]]:
        pass

class ChatBackend(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], model: str = "gpt-4") -> str:
        pass


### === Concrete Backends === ###

# OpenAI Backend
try:
    from openai import OpenAI as OpenAIClient
    _use_new_sdk = True
except ImportError:
    import openai as OpenAIClient
    _use_new_sdk = False

class OpenAIEmbedder(EmbeddingBackend):
    def __init__(self, model="text-embedding-3-small"):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        print("OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))
        self.client = OpenAIClient(api_key=self.api_key) if _use_new_sdk else None

    def embed(self, inputs):
        if _use_new_sdk:
            response = self.client.embeddings.create(input=inputs, model=self.model)
            return [d.embedding for d in response.data]
        else:
            OpenAIClient.api_key = self.api_key
            response = OpenAIClient.Embedding.create(input=inputs, model=self.model)
            return [d["embedding"] for d in response["data"]]

class OpenAIChat(ChatBackend):
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        print("OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))

        self.client = OpenAIClient(api_key=self.api_key) if _use_new_sdk else None

    def chat(self, messages, model="gpt-4"):
        if _use_new_sdk:
            res = self.client.chat.completions.create(model=model, messages=messages)
            return res.choices[0].message.content
        else:
            res = OpenAIClient.ChatCompletion.create(model=model, messages=messages)
            return res["choices"][0]["message"]["content"]


### === Central Router === ###

class AIRouter:
    def __init__(self, embedder: EmbeddingBackend, chatter: ChatBackend):
        self.embedder = embedder
        self.chatter = chatter

    def embed(self, inputs: list[str]) -> list[list[float]]:
        return self.embedder.embed(inputs)

    def chat(self, messages: list[dict], model="gpt-4") -> str:
        return self.chatter.chat(messages, model)


### === Factory === ###

def get_router(source="openai") -> AIRouter:
    if source == "openai":
        return AIRouter(OpenAIEmbedder(), OpenAIChat())
    else:
        raise ValueError(f"Unknown AI source: {source}")
