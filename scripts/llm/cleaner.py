import re
import unicodedata
import spacy
import contractions

# Load spaCy model once
_nlp = spacy.load("en_core_web_sm")

def clean_text(raw_text: str) -> str:
    """
    Cleans informal or speech-derived text by:
    1. Normalizing encoding and contractions.
    2. Removing redundant filler/interjection words based on linguistic structure.
    3. Outputting a cleaned, semantically denser version for downstream processing.
    """
    prepped = _preprocess_text(raw_text)
    doc = _nlp(prepped)
    cleaned_tokens = _filter_tokens(doc)
    print(" ".join(cleaned_tokens).strip() + "\n\n\n")
    return " ".join(cleaned_tokens).strip()


# --- Internal helpers ---

def _preprocess_text(text: str) -> str:
    text = _normalize_unicode(text)
    text = _expand_contractions(text)
    text = _collapse_noise(text)
    return text

def _normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)

def _expand_contractions(text: str) -> str:
    return contractions.fix(text)

def _collapse_noise(text: str) -> str:
    text = re.sub(r"\.{2,}", ".", text)     # collapse repeated periods
    text = re.sub(r"\s{2,}", " ", text)     # collapse excess spaces
    text = re.sub(r",{2,}", ",", text)      # collapse repeated commas
    return text.strip()

def _filter_tokens(doc):
    cleaned = []
    for i, token in enumerate(doc):
        if token.pos_ == "INTJ":
            continue  # remove interjections like "well", "uh", "oh"
        if i == 0 and token.pos_ == "ADV":
            continue  # skip sentence-initial adverbs like "basically", "actually"
        if token.text.lower() in {"you know", "i mean", "sort of", "kind of"}:
            continue  # classic hedge phrases
        if token.is_space or token.is_punct:
            continue
        cleaned.append(token.text)
    return cleaned
