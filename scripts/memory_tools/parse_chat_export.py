import json
from pathlib import Path

EXPORT_JSON = Path("/home/squinlan/Downloads/chatgpt_conversations_2025-05-01-15-17-37.zip")
EXTRACT_DIR = Path("/tmp/cliff_chat_export")
OUTPUT_JSONL = Path("../memory/personal/chat_export.jsonl")

import zipfile

# Extract ZIP if needed
with zipfile.ZipFile(EXPORT_JSON, "r") as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)

# Load conversations.json
conv_file = EXTRACT_DIR / "conversations.json"
if not conv_file.exists():
    raise FileNotFoundError("Could not find conversations.json after extraction.")

data = json.loads(conv_file.read_text())

with OUTPUT_JSONL.open("w", encoding="utf-8") as out_f:
    for convo in data:
        title = convo.get("title", "Untitled")
        create_time = convo.get("create_time")
        messages = []

        for mapping in convo.get("mapping", {}).values():
            message = mapping.get("message", {})
            if not message:
                continue  # skip null entries

            role = message.get("author", {}).get("role", "")

            parts = message.get("content", {}).get("parts", [])
            if parts:
                cleaned_parts = [p if isinstance(p, str) else json.dumps(p) for p in parts]
                messages.append(f"[{role}] {' '.join(cleaned_parts)}")


        if not messages:
            continue

        full_text = "\n\n".join(messages)
        out_f.write(json.dumps({
            "title": title,
            "timestamp": create_time,
            "text": full_text
        }) + "\n")

print(f"✅ Exported {len(data)} conversations to: {OUTPUT_JSONL.resolve()}")

