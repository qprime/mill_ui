import re

from scripts.llm.distill_text import distill_text

def call_distiller(input_text):
    # Call the actual distiller. (No need for stub, just use real function now)
    result = distill_text(input_text, guidance={}, strict_mode=False)
    return result.get("distilled_text", "")

def main():
    test_cases = [
        {
            "input": "Refactor completed. Merged into dev branch.",
            "expect_nonempty": True
        },
        {
            "input": "List all top-level folders.",
            "expect_nonempty": False
        },
        {
            "input": "What are the current tasks?",
            "expect_nonempty": False
        },
        {
            "input": "System update scheduled for 4pm.",
            "expect_nonempty": True
        },
        {
            "input": "Hi Cliff, just checking in!",
            "expect_nonempty": False
        },
        {
            "input": "I created a new 'tests/' directory for the project.",
            "expect_nonempty": True
        },
        {
            "input": "Please summarize the last 15 minutes.",
            "expect_nonempty": False
        },
        {
            "input": "Bug fixed in context_loader.py (line 42).",
            "expect_nonempty": True
        },
        # Add some NA test cases!
        {
            "input": "NA",
            "expect_nonempty": False
        },
        {
            "input": "N/A",
            "expect_nonempty": False
        },
        {
            "input": "none",
            "expect_nonempty": False
        },
    ]

    for idx, case in enumerate(test_cases):
        print(f"\n--- TEST {idx+1} ---")
        print(f"Input: {case['input']}")
        distilled = call_distiller(case["input"])
        print(f"Distilled: {repr(distilled)}")
        if case["expect_nonempty"]:
            assert distilled and distilled.lower() not in {"na", "n/a", "none", "na.", "n.a."}, \
                f"Expected distilled content, got: {repr(distilled)}"
        else:
            assert not distilled or distilled.lower() in {"na", "n/a", "none", "na.", "n.a."}, \
                f"Expected EMPTY or NA distilled content, got: {repr(distilled)}"
        print("PASS")

if __name__ == "__main__":
    main()
