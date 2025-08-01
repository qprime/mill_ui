"""
[testing] Unit tests for continuum.diff_tools module.
"""

import pytest
from continuum.diff_tools import get_unified_diff, side_by_side_diff, has_changes


def test_has_changes():
    assert not has_changes("same", "same")
    assert has_changes("a", "b")


def test_get_unified_diff():
    a = "line1\nline2\n"
    b = "line1\nline2 modified\n"
    diff = get_unified_diff(a, b, filename="testfile")
    assert "testfile.old" in diff
    assert "testfile.new" in diff
    assert "-line2" in diff
    assert "+line2 modified" in diff


def test_side_by_side_diff():
    a = "left1\nleft2"
    b = "right1\nright2"
    diff = side_by_side_diff(a, b, width=10)
    assert len(diff) == 2
    assert diff[0] == "left1      | right1"
    assert diff[1] == "left2      | right2"

