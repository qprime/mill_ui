import cv2
import numpy as np

def load_heightmap(png_path, scale_xy=0.1, scale_z=2.0):
    img = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Could not load image at {png_path}")

    # Force grayscale if needed
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    img = img.astype(np.float32)

    # Normalize based on bit depth
    max_val = 65535.0 if img.max() > 255 else 255.0
    img /= max_val

    heightmap = img * scale_z
    return heightmap, scale_xy
