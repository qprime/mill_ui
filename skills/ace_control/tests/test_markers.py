from skills.ace_control.markers import ContextRequest, MarkerSections, parse_markers


def test_parse_basic_sections():
    text = """
===PLAN===
- do a thing

===PATCH===
--- a/foo.py
+++ b/foo.py
@@

===COMMANDS===
git status
git diff

===TESTS===
pytest tests/foo_test.py

===ARTIFACTS===
docs/report.md

===NOTES===
All good

===CONTEXT_REQUESTS===
READ foo.py lines=10-40
READ bar.py summary
"""
    sections = parse_markers(text)
    assert sections.plan.strip().startswith("- do a thing")
    assert "--- a/foo.py" in sections.patch
    assert sections.commands == ["git status", "git diff"]
    assert sections.tests == ["pytest tests/foo_test.py"]
    assert sections.artifacts == ["docs/report.md"]
    assert sections.notes == "All good"
    assert len(sections.context_requests) == 2
    assert sections.context_requests[0] == ContextRequest(path="foo.py", start=10, end=40, summary=False)
    assert sections.context_requests[1] == ContextRequest(path="bar.py", start=None, end=None, summary=True)


def test_unknown_markers_preserved():
    text = """
===PLAN===
Step 1
===CUSTOM===
value
"""
    sections = parse_markers(text)
    assert sections.plan == "Step 1"
    assert sections.extras["CUSTOM"].strip() == "value"
