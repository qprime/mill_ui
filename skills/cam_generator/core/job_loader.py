# path: skills/cam_generator/core/job_loader.py
# type: configuration loader
# tags: cam, job, config, utils
# owner: cliff
# depends_on: pyyaml
# description: Loads and parses YAML job configuration files for CAM generation.

import yaml
from pathlib import Path


def load_job_config(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Job config not found: {path }")
    with open(path, "r") as f:
        return yaml.safe_load(f)
