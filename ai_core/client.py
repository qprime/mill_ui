"""
[AI Core Module] - OpenAI Client Interface

Minimal, agent-optimized OpenAI client for chat completions and embeddings.
- Imports and API key checks are at module load time for immediate failure.
- All functions require explicit model name (no hardcoded defaults).
- Errors are surfaced with clear RuntimeError messages for agent pipelines.
"""

import os
import openai

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set in environment.")

client = openai.OpenAI(api_key=api_key)

def get_chat_completion(messages, model, **kwargs):
    """
    Call the OpenAI Chat Completion API.
    Returns: str (model reply content)
    Raises: RuntimeError on failure.
    """
    try:
        resp = client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        return resp.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"OpenAI chat completion failed: {e}")

def get_embedding(input, model, **kwargs):
    """
    Call the OpenAI Embedding API.
    Returns: list (embedding vectors)
    Raises: RuntimeError on failure.
    """
    try:
        resp = client.embeddings.create(input=input, model=model, **kwargs)
        return [d.embedding for d in resp.data]
    except Exception as e:
        raise RuntimeError(f"OpenAI embedding call failed: {e}")
