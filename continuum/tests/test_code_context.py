import pytest

from continuum.code_context import (
    scrub_whitespace,
    strip_non_header_comments_and_docstrings,
    count_tokens,
)


def test_scrub_whitespace_reduces_blanks_and_crlf():
    text = "line1   \n\n\nline2\r\nline3\r"
    cleaned = scrub_whitespace(text)
    assert "\n\n" in cleaned  # collapsed 3 -> 2
    assert "\r" not in cleaned
    assert cleaned.count("\n") >= 3


def test_strip_non_header_comments_and_docstrings():
    code = (
        "# path: demo.py\n"
        "# description: sample\n"
        "\n"
        "\"\"\"Module docstring\"\"\"\n"
        "x = 1  # keep code, drop trailing comments\n"
        "# inline-comment-only\n"
        "def foo():\n"
        "    \"\"\"docstring\"\"\"\n"
        "    return x  # and trailing\n"
    )
    out = strip_non_header_comments_and_docstrings(code)
    assert "Module docstring" not in out
    assert "inline-comment-only" not in out
    assert "#" not in out  # no trailing comments
    assert "def foo()" in out
    assert "return x" in out


def test_count_tokens_small_text():
    n = count_tokens("one two three", model_name="gpt-4.1")
    assert isinstance(n, int)
    assert n >= 3

