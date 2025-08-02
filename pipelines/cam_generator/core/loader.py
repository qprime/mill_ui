"""
[pipeline]
TODO: describe module functionality.
"""

import cv2
import numpy as np
from cam_generator.core.job_loader import load_job_config


def load_heightmap(png_path, scale_xy=0.1, scale_z=2.0):
    job_config = load_job_config("config/job_config.yaml")
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
