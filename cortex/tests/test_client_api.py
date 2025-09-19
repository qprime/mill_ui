# path: cortex/tests/test_client_api.py
# type: integration api tests
# tags: pytest, api, openai, minimal_tokens
# owner: cliff
# depends_on: cortex/client.py
# description: Positive API calls to OpenAI with minimal tokens/cost.

import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set; skipping live OpenAI API tests",
)

def _chat_model() -> str:
    # Use a widely-available, low-cost model by default
    return os.getenv("OPENAI_TEST_CHAT_MODEL", "gpt-4o-mini")


def _embed_model() -> str:
    return os.getenv("OPENAI_TEST_EMBED_MODEL", "text-embedding-3-small")


@pytest.mark.api
@pytest.mark.network
def test_openai_chat_min_tokens():
    pytest.importorskip("openai")
    from cortex.client import get_chat_completion
    messages = [{"role": "user", "content": "Reply with OK"}]
    reply = get_chat_completion(messages, model=_chat_model(), max_tokens=5, temperature=0)
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0


@pytest.mark.api
@pytest.mark.network
def test_openai_embedding_minimal():
    pytest.importorskip("openai")
    from cortex.client import get_embedding
    vecs = get_embedding(["hello"], model=_embed_model())
    assert isinstance(vecs, list)
    assert len(vecs) == 1
    assert isinstance(vecs[0], list)
    assert len(vecs[0]) > 100  # don't assert exact dimensionality
