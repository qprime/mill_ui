"""
[testing] Unit tests for memory.memory_graph.describe_purpose function.
"""

import pytest
from memory.memory_graph import describe_purpose


@pytest.mark.parametrize(
    "name,expected",
    [
        ("development", "Active project code memory (chunks, annotations, summaries)"),
        ("cliff_state", "CLI usage logs and local system context"),
        ("unknown", "Unclassified memory domain"),
    ],
)
def test_describe_purpose(name, expected):
    assert describe_purpose(name) == expected
