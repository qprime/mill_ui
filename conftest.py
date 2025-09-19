import os
import sys
from pathlib import Path


def pytest_configure(config):
    # Ensure project root is importable
    root = Path(__file__).parent.resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # Provide a harmless default API key for import safety on machines
    # without configured secrets (e.g., CI or fresh environments).
    os.environ.setdefault("OPENAI_API_KEY", "test-key")

