from skills.living_truth_partner.md_index import MarkdownIndex

def test_markdown_index_sections():
    text = "\n".join([
        "# Heading One",
        "Content line", 
        "## Sub Heading",
        "More text",
        "# Second",
        "Wrap"
    ])
    index = MarkdownIndex.build(text)
    sections = index.sections()
    ids = [section.id for section in sections]
    assert ids[0] == "heading-one"
    assert ids[1] == "sub-heading"
    assert ids[2] == "second"
    portion = index.slice(text, "sub-heading").strip()
    assert "More text" in portion
    replaced = index.replace(text, "heading-one", "# Heading One\nNew content\n")
    assert "New content" in replaced
