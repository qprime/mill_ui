import pytest
import time
from scripts.llm.distill_text import distill_text

# Test cases: (input, expect_nonempty, expect_bypassed)
CASES = [
    ("Refactor completed. Merged into dev branch.", True, False),
    ("List all top-level folders.", False, True),
    ("What are the current tasks?", False, True),
    ("System update scheduled for 4pm.", True, False),
    ("Hi Cliff, just checking in!", False, True),
    ("I created a new 'tests/' directory for the project.", True, False),
    ("Please summarize the last 15 minutes.", False, True),
    ("Bug fixed in context_loader.py (line 42).", True, False),
    ("NA", False, True),
    ("N/A", False, True),
    ("none", False, True),
    # Add more cases here as you refine your prompt/logic!
]

@pytest.mark.parametrize("input_text,expect_nonempty,expect_bypassed", CASES)
def test_distiller(input_text, expect_nonempty, expect_bypassed, capsys):
    start = time.time()
    result = distill_text(input_text, guidance={}, strict_mode=False)
    elapsed = time.time() - start

    distilled = result.get("distilled_text", "")
    bypassed = result.get("metadata", {}).get("bypassed", False)
    fallback = result.get("metadata", {}).get("fallback", False)

    # Print for *every* test run, not just on failure
    print(
        f"\nInput:      {input_text!r}\n"
        f"Distilled:  {distilled!r}\n"
        f"Bypassed:   {bypassed}\n"
        f"Fallback:   {fallback}\n"
        f"Elapsed:    {elapsed:.2f}s\n"
        f"{'-'*40}"
    )

    # Assert backend was (or wasn't) called as expected
    assert bypassed == expect_bypassed, f"Expected bypassed={expect_bypassed}, got {bypassed} for input: {input_text!r}"

    # Assert content according to updated logic
    if expect_nonempty:
        assert distilled.strip(), f"Expected distilled content, got: {repr(distilled)}"
        assert distilled.lower() not in {"na", "n/a", "none", "na.", "n.a."}, f"Expected *not* NA/none, got: {repr(distilled)}"
    else:
        # For "bypassed" cases, allow empty, NA, or original text as fallback
        assert not distilled or \
               distilled.lower() in {"na", "n/a", "none", "na.", "n.a."} or \
               distilled == input_text, \
            f"Expected EMPTY, NA, or fallback (original) for: {repr(input_text)}, got: {repr(distilled)}"

def test_api_call_time():
    import time
    t0 = time.time()
    result = distill_text("This is a factual update for the database.", guidance={}, strict_mode=False)
    elapsed = time.time() - t0
    # Accept fast calls as real (lowered threshold for speed)
    assert elapsed > 0.2, f"API call seems too fast ({elapsed:.2f}s) — may not have called backend"
