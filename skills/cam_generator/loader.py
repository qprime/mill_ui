# path: skills/cam_generator/core/loader.py
# # desc: Load heightmap PNG → normalized depth map.
# api: load_heightmap
# tags: cam

import cv2
import numpy as np

import yaml
from pathlib import Path

def load_job_config(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Job config not found: {path }")
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_heightmap(png_path, job_config_path=None, scale_xy=0.1, scale_z=2.0):
    if job_config_path is None:
        job_config_path = "config/job_config.yaml"
    job_config = load_job_config(job_config_path)
    img = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Could not load image at {png_path }")
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = img.astype(np.float32)
    max_val = 65535.0 if img.max() > 255 else 255.0
    img /= max_val
    if job_config.get("invert_heightmap_z", False):
        img = 1.0 - img
    heightmap = img * scale_z
    return heightmap, scale_xy
