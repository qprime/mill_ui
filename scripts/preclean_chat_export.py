from pathlib import Path
import json
import re

input_path = Path("../memory/personal/chat_export.jsonl")
output_path = Path("../memory/personal/chat_prepped.jsonl")

def clean_text(raw_text):
    lines = raw_text.splitlines()
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        # Skip file uploads and code/data attachments
        if re.search(r"(User uploaded file|file-[\w\d]+|\.(png|jpg|jpeg|pdf|py|sh|log|zip|txt))", line, re.IGNORECASE):
            continue

        # Skip CLI echo prompts
        if re.match(r".*@.*:\~\$ ", line):
            continue

        # Remove "Logged and pushed" junk
        if "Logged and pushed:" in line:
            continue

        # Collapse debug output markers
        if "Traceback (most recent call last):" in line:
            cleaned_lines.append("[debug output omitted]")
            continue

        cleaned_lines.append(line)

    # Clean up blank line spam
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

with input_path.open("r", encoding="utf-8") as infile, output_path.open("w", encoding="utf-8") as outfile:
    for line in infile:
        try:
            entry = json.loads(line)
            entry["text"] = clean_text(entry["text"])
            outfile.write(json.dumps(entry) + "\n")
        except Exception as e:
            print("⚠️ Failed to parse line:", e)

print(f"✅ Cleaned output written to: {output_path.resolve()}")

