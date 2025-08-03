"""
[AI Core Module] - OpenAI Client Interface

Unified, agent-optimized client for all OpenAI API calls:
- Chat completions
- Embeddings
- Image generations (DALL·E/gpt-image-1)

All API key logic is loaded at module import for immediate failure.
Errors are surfaced as RuntimeError for all agent pipelines.
"""

import os
import openai
import requests

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set in environment.")

client = openai.OpenAI(api_key=api_key)

# --- Chat Completion (via SDK)
def get_chat_completion(messages, model, **kwargs):
    """
    Call the OpenAI Chat Completion API.
    Returns: str (model reply content)
    Raises: RuntimeError on failure.
    """
    try:
        resp = client.chat.completions.create(model=model, messages=messages, **kwargs)
        return resp.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"OpenAI chat completion failed: {e}")

# --- Embedding (via SDK)
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

# --- Image Generation (DALL·E, gpt-image-1; via direct HTTP)
def get_image_generation(prompt, model="gpt-image-1", size="1024x1024", n=1):
    """
    Call the OpenAI Image Generation API (DALL·E/gpt-image-1).
    Returns: list of base64 PNG image data.
    Raises: RuntimeError on failure.
    """
    API_URL = "https://api.openai.com/v1/images/generations"
    HEADERS = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": n,
    }
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        data = response.json()
        return [item["b64_json"] for item in data["data"]]
    except Exception as e:
        try:
            err_detail = response.json()
        except Exception:
            err_detail = response.text if 'response' in locals() else str(e)
        raise RuntimeError(f"OpenAI image generation failed: {err_detail}")

