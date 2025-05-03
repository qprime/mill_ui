import os
import json

debug_dir = "/home/squinlan/cliff_ai/memory/personal/debug_outputs"
output_file = "/home/squinlan/cliff_ai/memory/personal/chat_cleaned_raw_fallback.jsonl"

count = 0
with open(output_file, "w") as outfile:
    for fname in sorted(os.listdir(debug_dir)):
        if not fname.endswith(".txt"):
            continue

        full_path = os.path.join(debug_dir, fname)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    print(f"⚠️ Empty file: {fname}")
                    continue

            entry = {
                "title": fname.replace("_chunk", " (chunk ").replace(".txt", ")"),
                "chunk": fname,
                "text": content,
                "messages": [],
                "topic": "",
                "notes": "",
                "source": "raw_fallback"
            }

            outfile.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1
            print(f"✅ Added fallback for: {fname}")

        except Exception as e:
            print(f"❌ Error processing {fname}: {e}")

print(f"\n🎉 Fallback salvage complete: {count} entries written to {output_file}")

