# path: pipelines/image_pipeline/test_enhancement.py
# type: test module
# tags: image, enhancement, test, visualization
# owner: cliff
# depends_on: pipelines/image_pipeline/enhance.py
# description: Compares original and enhanced images from image pipeline for testing purposes.

import numpy as np
import cv2
import matplotlib.pyplot as plt
from pipelines.image_pipeline.enhance import enhance_heightmap


def load_image(image_path: str):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path }")
    return img


def plot_comparison(
    original_img,
    enhanced_img,
    title="Enhanced Image",
    save_path="output_comparison.png",
):
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    axes[0].imshow(original_img, cmap="gray")
    axes[0].set_title("Original Image")
    axes[0].axis("off")

    axes[1].imshow(enhanced_img, cmap="gray")
    axes[1].set_title(title)
    axes[1].axis("off")

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    print(f"Comparison saved to {save_path }")
    plt.close()


def test_enhancement(image_path, config):
    img_8bit = load_image(image_path)
    enhanced_img = enhance_heightmap(img_8bit, config)
    plot_comparison(img_8bit, enhanced_img)


config = {
    "enhance_heightmap": True,
    "enhancement": {
        "z_curve_power": 0.9,
        "flatten_background": True,
        "background_cutoff": 0.05,
        "blur_sigma": 0.3,
        "edge_boost": False,
        "edge_boost_weight": 0.025,
        "z_scale_mm": 0.0,
        "auto_normalize": True,
    },
}

if __name__ == "__main__":
    image_path = "output/flamingo/image.png"
    test_enhancement(image_path, config)
