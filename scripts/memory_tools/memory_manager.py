import os
import json
import chromadb
from chromadb.config import Settings
from datetime import datetime

class MemoryManager:
    def __init__(self, memory_root="~/cliff_ai/memory", config_file="~/cliff_ai/config/memory_domains.json"):
        self.memory_root = os.path.expanduser(memory_root)
        self.config_file = os.path.expanduser(config_file)
        self.domains = self.load_domains()
        self.clients = {}
        self._initialize_clients()

    def load_domains(self):
        with open(self.config_file, "r") as f:
            data = json.load(f)
        return [domain["name"] for domain in data["domains"]]

    def _initialize_clients(self):
        for domain in self.domains:
            domain_path = os.path.join(self.memory_root, domain)
            os.makedirs(domain_path, exist_ok=True)

            client = chromadb.PersistentClient(path=domain_path)

            # Create or get a collection
            collection = client.get_or_create_collection(name="memory")
            self.clients[domain] = collection


    def add_to_domain(self, domain, text, source="manual_entry", tags=None):
        if domain not in self.clients:
            raise ValueError(f"Domain '{domain}' not found.")

        timestamp = datetime.utcnow().isoformat()
        metadata = {
            "timestamp": timestamp,
            "source": source,
            "tags": ", ".join(tags) if tags else ""
        }

        collection = self.clients[domain]
        collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[f"{domain}-{timestamp}"]
        )


    def query_domain(self, domain, query_text, n_results=5):
        if domain not in self.clients:
            raise ValueError(f"Domain '{domain}' not found.")

        collection = self.clients[domain]
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results

    def query_all_domains(self, query_text, n_results=3):
        combined_results = []
        for domain in self.domains:
            collection = self.clients[domain]
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            combined_results.append((domain, results))
        return combined_results

if __name__ == "__main__":
    mm = MemoryManager()

    # Example test add:
    mm.add_to_domain(domain="personal", text="This is a test memory from CLI.", source="manual_entry", tags=["test", "cli"])

    # Example test query:
    result = mm.query_domain(domain="personal", query_text="test memory")
    print(result)

