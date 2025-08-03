# path: tests/unit/test_code_context.py
# type: unit_tests
# tags: testing, code_context, utils
# owner: cliff
# depends_on: continuum/code_context.py
# description: Unit tests for code context utilities in the continuum package.

import os
import tempfile
from continuum.code_context import (
    should_include_file,
    should_exclude_dir,
    scrub_whitespace,
    count_tokens,
    get_top_level_docstring,
)


def test_should_include_file():
    assert should_include_file("file.py")
    assert should_include_file("index.html")
    assert not should_include_file("file.txt")


def test_should_exclude_dir():
    assert should_exclude_dir(".git")
    assert should_exclude_dir("__pycache__")
    assert not should_exclude_dir("src")


def test_scrub_whitespace():
    text = "line1   \n\n\nline2\r\nline3\r"
    cleaned = scrub_whitespace(text)
    # Ensure consecutive blank lines are reduced and no carriage returns remain
    assert "\n\n" in cleaned
    assert "line1" in cleaned
    assert "\r" not in cleaned


def test_count_tokens():
    assert count_tokens("one two three") == 3


def test_get_top_level_docstring():
    code = '''
    """Module docstring."""
    some_code = 1
    '''
    assert get_top_level_docstring(code) == '"""Module docstring."""'
    no_doc = "some_code = 1"
    assert get_top_level_docstring(no_doc) == ""
