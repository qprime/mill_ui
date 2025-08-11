# path: skills/cam_generator/core/job_loader.py
# # desc: Read job_config.yaml.
# api: load_job_config
# tags: cam

import yaml
from pathlib import Path

def load_job_config(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Job config not found: {path }")
    with open(path, "r") as f:
        return yaml.safe_load(f)
