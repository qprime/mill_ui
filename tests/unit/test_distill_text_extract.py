"""
[testing] Unit tests for ai_core.distill_text.extract_distilled_block function.
"""

import pytest
from ai_core.distill_text import extract_distilled_block


@pytest.mark.parametrize("input_text,expected", [
    ("<<<DISTILL_START\ncontent\nDISTILL_END>>>", "content"),
    ("prefix <<<DISTILL_START   content   DISTILL_END>>> suffix", "content"),
    ("no markers here", None),
    ("<<<DISTILL_START\nNA\nDISTILL_END>>>", None),
    ("<<<DISTILL_START\nnone\nDISTILL_END>>>", None),
])
def test_extract_distilled_block(input_text, expected):
    assert extract_distilled_block(input_text) == expected
