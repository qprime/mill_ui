#!/usr/bin/env python3
"""
batch_clean_chat.py v6

Stable and verbose logging:
- Logs fallback parse success
- Suppresses error messages on fallback success
- Tracks chunks per entry
"""
import json
import os
import openai
import re
import time
import ast
from pathlib import Path
from datetime import datetime
from http.client import RemoteDisconnected

# Configuration
INPUT_PATH = Path("../memory/personal/chat_prepped.jsonl")
OUTPUT_PATH = Path("../memory/personal/chat_cleaned.jsonl")
CHUNK_WORDS = 800
MAX_ENTRIES = 3
MAX_CHUNKS = 5
DEBUG_OUTPUT_DIR = Path("../memory/personal/debug_outputs")
DEBUG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

openai.api_key = os.getenv("OPENAI_API_KEY")

def split_text_into_chunks(text, max_words=CHUNK_WORDS):
    words = text.split()
    return [' '.join(words[i:i + max_words]) for i in range(0, len(words), max_words)]

def parse_json_flex(raw):
    try:
        return json.loads(raw), "json"
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(raw), "fallback"
        except Exception:
            return None, "fail"

def clean_chunk(chunk, entry_title="untitled", chunk_index=0):
    prompt = f"""
    You are a conversation cleaner. Here's your task:

    1. Remove all redundant or repetitive lines.
    2. Drop filler unless it adds meaning.
    3. Keep important technical detail, logic, or architecture.
    4. Return this JSON:
    {{
      "cleaned_text": "...",
      "topics": ["...", "..."]
    }}

    Text:
    {chunk}
    """.strip()

    for attempt in range(3):
        try:
            res = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Only respond with valid JSON. No preamble, no commentary. No markdown or explanation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.4,
            )
            raw = res.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw).strip()
            raw = raw.replace('“', '"').replace('”', '"')

            match = re.search(r'{\s*"cleaned_text":.*}', raw, re.DOTALL)
            if match:
                parsed, method = parse_json_flex(match.group(0))
                if parsed:
                    print(f"✅ Chunk {chunk_index} succeeded ({method}).")
                    return parsed
            debug_file = DEBUG_OUTPUT_DIR / f"{entry_title[:40].replace(' ', '_')}_chunk{chunk_index}.txt"
            debug_file.write_text(raw)
            print(f"❌ Chunk {chunk_index} failed. Saved raw output to: {debug_file}")
        except RemoteDisconnected:
            print("⚠️ RemoteDisconnected — retrying...")
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ GPT error on attempt {attempt+1}: {e}")
            time.sleep(1)

    return {"cleaned_text": "[Parse failed]", "topics": []}

def clean_conversation(entry):
    chunks = split_text_into_chunks(entry["text"])
    results, topics = [], set()

    #for i, chunk in enumerate(chunks[:MAX_CHUNKS]):
    for i, chunk in enumerate(chunks):
        print(f"🧠 Cleaning '{entry.get('title', 'untitled')}' — chunk {i+1}/{len(chunks)}")
        cleaned = clean_chunk(chunk, entry.get("title", "untitled"), i + 1)
        if cleaned["cleaned_text"] != "[Parse failed]":
            results.append(cleaned["cleaned_text"])
            topics.update(cleaned["topics"])
        else:
            print(f"⚠️ Chunk {i+1} skipped.")

    if results:
        print(f"🔢 Saved {len(results)} cleaned chunks for: {entry.get('title', 'untitled')}")
        return {
            "source": entry.get("source", "unknown"),
            "title": entry.get("title", "untitled"),
            "timestamp": entry.get("timestamp"),
            "cleaned_text": "\n\n".join(results),
            "topics": sorted(topics)
        }

    print(f"⚠️ No valid cleaned content for: {entry.get('title', 'untitled')}")
    return None

# Main execution loop
entries_processed = 0
with INPUT_PATH.open("r", encoding="utf-8") as infile:
    for line in infile:
        #if entries_processed >= MAX_ENTRIES:
        #    break

        entry = json.loads(line)
        result = clean_conversation(entry)

        if result:
            with OUTPUT_PATH.open("a", encoding="utf-8") as outfile:
                outfile.write(json.dumps(result) + "\n")
            print(f"[{datetime.now().isoformat()}] ✅ Saved: {entry.get('title', 'untitled')}")
        else:
            print(f"⚠️ Skipped saving entry: {entry.get('title', 'untitled')}")

        entries_processed += 1

print(f"\n🎉 Batch complete. Cleaned output written to: {OUTPUT_PATH.resolve()}")
