import random
from memory_manager import MemoryManager

# Initialize the Memory Manager
mm = MemoryManager()

# Some example texts to inject
fake_memories = [
    {
        "domain": "personal",
        "text": "Ordered new books on woodworking and AI.",
        "source": "manual_entry",
        "tags": ["books", "learning"]
    },
    {
        "domain": "production",
        "text": "Completed setup of the new CNC spindle cooling system.",
        "source": "lab_manager",
        "tags": ["cnc", "maintenance"]
    },
    {
        "domain": "accounting",
        "text": "Filed Q2 tax documents and updated expense ledger.",
        "source": "manual_entry",
        "tags": ["taxes", "finance"]
    },
    {
        "domain": "research",
        "text": "Collected initial performance data on AI voice transcription speeds.",
        "source": "voice_input",
        "tags": ["research", "voice", "benchmarking"]
    },
    {
        "domain": "production",
        "text": "G-code sender failed during job #144; rebooted system and resumed.",
        "source": "cli_logger",
        "tags": ["gcode", "error", "recovery"]
    }
]

def populate_fake_data():
    for memory in fake_memories:
        mm.add_to_domain(
            domain=memory["domain"],
            text=memory["text"],
            source=memory["source"],
            tags=memory["tags"]
        )
    print("✅ Populated fake memory entries.")

def quick_query(domain="production", query="setup"):
    print(f"🔍 Querying domain '{domain}' for '{query}':")
    results = mm.query_domain(domain, query)
    print(results)

if __name__ == "__main__":
    populate_fake_data()
    quick_query(domain="production", query="setup")

