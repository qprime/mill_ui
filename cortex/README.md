# Cortex Router

Owner path: cortex/

## 1. What this is

Cortex routes chat, embedding, and image calls through a thin provider abstraction.
It centralises API credentials, persona lookups, and client fallbacks for the rest of the stack.

## 2. When to use it

- Request embeddings or chat completions from the configured LLM provider.
- Generate persona-styled prompts or images for CAM and documentation flows.
- Extend the stack with new model providers or offline routing strategies.

## 3. How to run

Provide OpenAI credentials, then exercise the router or run its tests directly.

```bash
export OPENAI_API_KEY=sk-your-key # replace with a valid token
python - <<'PY'
from cortex.ai_router import get_router
router = get_router()
print(router.embed(["ping"])[0][:4])
print(router.chat([{"role": "user", "content": "ping"}]))
PY
pytest -q cortex/tests/test_client_api.py
```

## 4. Inputs & outputs (for AI & humans)

- `OPENAI_API_KEY` — environment variable consumed by `cortex.client`.
- `cortex/personas/` — persona and style metadata used to assemble prompts.
- `cortex/client.py` — provider bindings wrapping SDK and HTTP calls.
- `memories/` — optional transcripts and artifacts referenced by higher-level callers.

## 5. Public surface

- `cortex.ai_router.get_router(source='openai')` — return the active `AIRouter` implementation.
- `AIRouter.embed(inputs, model='text-embedding-3-small')` — fetch embeddings for a list of strings.
- `AIRouter.chat(messages, model='gpt-4.1-mini')` — produce a chat completion response.
- `cortex.client.get_image_generation(prompt, model='gpt-image-1')` — request base64 PNG payloads.

## 6. Invariants & guardrails

- The router currently supports only the `openai` backend; add new identifiers deliberately.
- `OPENAI_API_KEY` must be set; helpers raise `RuntimeError` when credentials are missing.
- Persona and style metadata stay deterministic; avoid mutating the loaded dictionaries at runtime.
- Downstream callers must sanitize user content before invoking the client helpers.

## 7. Extension points

- Register new providers by extending `get_router` and supplying compatible client functions.
- Drop additional persona/style packs under `cortex/personas/` for new verticals.
- Wrap `AIRouter` methods with rate limiting or caching if deployments require it.

## 8. AI reading order

- `cortex/ai_router.py` — Router facade for chat and embeddings.
- `cortex/client.py` — OpenAI client bindings and HTTP fallbacks.
- `cortex/context_manager.py` — Context assembly helpers for prompts.
- `cortex/distill.py` — Document distillation utilities used by living docs.
- `cortex/personas/personas_manager.py` — Loads persona and style metadata.
