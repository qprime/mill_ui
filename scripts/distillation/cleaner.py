import re

def clean_text(raw_text: str) -> str:
    """
    Deterministically cleans input by removing false starts, filler phrases, and redundant language.
    Designed to prepare text for semantic distillation (Stage 2).
    """
    # Remove common filler phrases and false starts
    patterns = [
        r"\b(um+|uh+|like|you know|I mean)\b",          # filler
        r"\b(so+|okay+|well+)\b",                        # soft openers
        r"\b(let me think|what I’m trying to say)\b",   # hesitant phrasing
        r"\b(uh-huh|mm-hmm)\b",                          # nonverbal affirmations
    ]
    for p in patterns:
        raw_text = re.sub(p, "", raw_text, flags=re.IGNORECASE)

    # Collapse extra whitespace
    cleaned = re.sub(r"\s+", " ", raw_text).strip()
    return cleaned
