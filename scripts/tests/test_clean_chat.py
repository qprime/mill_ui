import json
import os
import openai
import re
from pathlib import Path

openai.api_key = os.getenv("OPENAI_API_KEY")

# Load original parsed chat log
CHAT_PATH = Path("../memory/personal/chat_export.jsonl")
OUTPUT_PATH = Path("../memory/personal/chat_clean_preview.jsonl")

sample = []
with CHAT_PATH.open("r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        sample.append(json.loads(line))

def clean_conversation(entry):
    from textwrap import wrap
    import time

    text = entry["text"]
    word_limit = 8000
    chunks = wrap(text, word_limit)

    cleaned_chunks = []
    topics = set()

    for i, chunk in enumerate(chunks):
        print(f"🧠 Cleaning chunk {i+1}/{len(chunks)}...")

        prompt = f"""
You are a conversation cleaning assistant. Here's your job:

1. Remove all redundant or repetitive lines.
2. Drop filler language or digressions unless they add emotional/contextual value.
3. Preserve meaningful technical details, questions, or decisions.
4. Identify main topics discussed in this chunk of a longer conversation.

Return this JSON format:
{{
  "cleaned_text": "...",
  "topics": ["...", "..."]
}}

Conversation chunk:
{chunk}
        """.strip()

        res = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.4
        )

        raw_response = res.choices[0].message.content.strip()

        try:
            # Extract anything that looks like a JSON object from the response
            match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if match:
                raw_response = match.group(0)
            else:
                print("❌ Couldn't extract JSON block. Full response:\n", raw_response)
                return {
                    "source": entry.get("source", "unknown"),
                    "title": entry.get("title", "untitled"),
                    "timestamp": entry.get("timestamp", None),
                    "cleaned_text": "[Parse failed]",
                    "topics": []
                }

            data = json.loads(raw_response)
        except json.JSONDecodeError:
            print("❌ Failed to parse JSON. Dumping response for review:")
            print(raw_response)
            return {
                "source": entry.get("source", "unknown"),
                "title": entry.get("title", "untitled"),
                "timestamp": entry.get("timestamp", None),
                "cleaned_text": "[Parse failed]",
                "topics": []
            }


        cleaned_chunks.append(data["cleaned_text"])
        topics.update(data["topics"])

        time.sleep(1)  # to respect rate limits

    return {
        "source": entry["source"],
        "title": entry["title"],
        "timestamp": entry["timestamp"],
        "cleaned_text": "\n\n".join(cleaned_chunks),
        "topics": sorted(topics)
    }


# Process and save preview
results = []
MAX_TOKENS = 8000

for entry in sample:
    print(f"🔍 Cleaning: {entry['title']}")
    
    print(f"📏 '{entry['title']}' is {len(entry['text'].split())} tokens")


    result = clean_conversation(entry)
    results.append(result)

with OUTPUT_PATH.open("w") as out:
    for r in results:
        out.write(json.dumps(r) + "\n")

print(f"\n✅ Saved preview to: {OUTPUT_PATH.resolve()}")

