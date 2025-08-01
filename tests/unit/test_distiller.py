import pytest
from ai_core.distill_text import distill_text

CASES = [
    "Refactor completed. Merged into dev branch.",
    "List all top-level folders.",
    "What are the current tasks?",
    "System update scheduled for 4pm.",
    "Hi Cliff, just checking in!",
    "I created a new 'tests/' directory for the project.",
    "Please summarize the last 15 minutes.",
    "Bug fixed in context_loader.py (line 42).",
    "NA",
    "N/A",
    "none",
]

@pytest.mark.parametrize("input_text", CASES)
def test_distiller_always_nonempty(input_text, capsys):
    result = distill_text(input_text, guidance={}, strict_mode=False)
    distilled = result.get("distilled_text", "")
    assert distilled.strip(), f"Distilled text was empty for input: {input_text!r}"

def test_api_call_time():
    import time
    t0 = time.time()
    result = distill_text("This is a factual update for the database.", guidance={}, strict_mode=False)
    elapsed = time.time() - t0
    assert elapsed > 0.2, f"API call seems too fast ({elapsed:.2f}s) — may not have called backend"
