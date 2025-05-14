#!/usr/bin/env python3
"""
debug_retry_parser.py (version 11, raw salvage mode)

Grabs any long quoted block of text and stores it as "cleaned_text".
Adds placeholder metadata for manual review later.
"""

import os
import json
import re
from pathlib import Path

INPUT_DIR = Path("../memory/personal/debug_outputs/")
OUTPUT_FILE = Path("../memory/personal/chat_cleaned_recovered.jsonl")
RECOVERED = []

def salvage_text(raw, filename):
    raw = raw.replace('“', '"').replace('”', '"').strip()
    matches = re.findall(r'"([^"]{100,})"', raw, re.DOTALL)
    if matches:
        return {
            "cleaned_text": matches[0].strip(),
            "topics": [],
            "title": filename.replace("_chunk", " — chunk ").replace(".txt", ""),
            "source": "debug_salvage",
            "timestamp": None,
            "notes": "salvaged text from loosely structured file"
        }
    return None

def main():
    print(f"📂 Scanning: {INPUT_DIR.resolve()}")
    count_valid = 0
    count_invalid = 0
    files_processed = 0

    for file in sorted(INPUT_DIR.glob("*.txt")):
        raw = file.read_text(encoding="utf-8")
        files_processed += 1
        result = salvage_text(raw, file.name)
        if result:
            RECOVERED.append(result)
            print(f"🩹 Salvaged: {file.name}")
            count_valid += 1
            try:
                file.unlink()
                print(f"🗑️ Deleted: {file.name}")
            except Exception as e:
                print(f"⚠️ Could not delete {file.name}: {e}")
        else:
            print(f"⚠️ Still unreadable: {file.name}")
            count_invalid += 1

    if RECOVERED:
        with OUTPUT_FILE.open("a", encoding="utf-8") as f:
            for entry in RECOVERED:
                f.write(json.dumps(entry) + "\n")
        print(f"\n🎉 {count_valid} text-only fragments salvaged and written to: {OUTPUT_FILE.resolve()}")
    else:
        print("\n❌ No additional fragments recovered.")

    print(f"🧮 Processed: {files_processed} files total.")
    print(f"✅ Valid: {count_valid} | ❌ Invalid: {count_invalid}")
    print("🛠 debug_retry_parser version = 11 (raw salvage mode)")

if __name__ == "__main__":
    main()
