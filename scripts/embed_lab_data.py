import json
from pathlib import Path
import chromadb
from chromadb.config import Settings

# Path to your .jsonl file
jsonl_path = Path("../memory/lab/lab_data.jsonl")
lines = jsonl_path.read_text().splitlines()
records = [json.loads(line) for line in lines]

# Connect to Chroma
client = chromadb.PersistentClient(path="../memory/lab")
collection = client.get_or_create_collection(name="lab_devices")

# Prepare entries
documents = []
metadatas = []
ids = []

for i, record in enumerate(records):
    summary = f"Device: {record.get('device_id')}\n"
    summary += "\n".join([f"{k}: {v}" for k, v in record.items() if k != "device_id"])
    documents.append(summary)
    metadatas.append({"source": "lab_data", "device_id": record["device_id"]})
    ids.append(f"lab-{i}")

collection.add(documents=documents, metadatas=metadatas, ids=ids)

print(f"✅ Embedded {len(documents)} devices into lab memory.")

