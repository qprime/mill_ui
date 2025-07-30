# scripts/llm/client.py

import os

try:
    import openai
    _openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except ImportError:
    _openai_client = None

def get_chat_completion(messages, model="gpt-4.1-mini", **kwargs):
    if not _openai_client:
        raise RuntimeError("OpenAI client not available.")
    resp = _openai_client.chat.completions.create(
        model=model, messages=messages, **kwargs
    )
    return resp.choices[0].message.content

def get_embedding(input, model="text-embedding-3-small", **kwargs):
    if not _openai_client:
        raise RuntimeError("OpenAI client not available.")
    resp = _openai_client.embeddings.create(input=input, model=model, **kwargs)
    return [d.embedding for d in resp.data]

# Add support for other providers here (Phi, Llama, etc.) as you expand.