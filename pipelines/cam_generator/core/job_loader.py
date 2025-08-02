"""
[pipeline]
TODO: describe module functionality.
"""

import yaml
from pathlib import Path


def load_job_config(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Job config not found: {path }")
    with open(path, "r") as f:
        return yaml.safe_load(f)
