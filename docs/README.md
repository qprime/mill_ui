readme_content = """
# 📚 Cliff AI — Documentation Overview

This folder contains internal documentation, system design notes, and module-specific overviews for the Cliff AI assistant.

---

## 📄 Included Files

| File Name                          | Description                                                      |
|-----------------------------------|------------------------------------------------------------------|
| `system_design_summary.md`        | Full architecture overview including phases, goals, and UI plans |
| `Cliff-lab-manager-overview.txt`  | In-depth breakdown of the Lab Manager module                     |
| `cliff_mistral_whisper_summary_1.txt` | Early exploration/summary for Whisper and Mistral integration   |

---

## 🧠 Usage

These documents are intended to:
- Guide development of new modules or features
- Serve as persistent memory Cliff can reference when making decisions
- Provide architectural clarity as the system scales

Consider linking relevant documents to tasks or memory entries via file path.

---

## 📌 Suggestions

- Keep module-specific docs named consistently with their folder/module
- For large design discussions, consider using Markdown so they can be rendered in the web UI
- Store high-signal content here that helps Cliff understand intent, not just raw logs

"""

readme_path = Path("docs/README.md")
readme_path.parent.mkdir(parents=True, exist_ok=True)
readme_path.write_text(readme_content.strip())
readme_path.exists()
