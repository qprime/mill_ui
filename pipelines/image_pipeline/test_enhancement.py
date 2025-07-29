import numpy as np
import cv2
import matplotlib.pyplot as plt
from image_pipeline.core.enhance import enhance_heightmap

# Load a sample image (8-bit grayscale heightmap)
def load_image(image_path: str):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found at {image_path}")
    return img

# Plot original vs enhanced images for comparison
def plot_comparison(original_img, enhanced_img, title="Enhanced Image", save_path="output_comparison.png"):
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    
    # Plot original
    axes[0].imshow(original_img, cmap='gray')
    axes[0].set_title("Original Image")
    axes[0].axis('off')
    
    # Plot enhanced
    axes[1].imshow(enhanced_img, cmap='gray')
    axes[1].set_title(title)
    axes[1].axis('off')
    
    plt.tight_layout()
    
    # Save figure to disk instead of showing it interactively
    plt.savefig(save_path, dpi=300)
    print(f"Comparison saved to {save_path}")
    plt.close()


# Test different enhancement algorithms
def test_enhancement(image_path, config):
    img_8bit = load_image(image_path)
    
    # Enhance the image using the enhancement pipeline
    enhanced_img = enhance_heightmap(img_8bit, config)
    
    # Visualize the comparison
    plot_comparison(img_8bit, enhanced_img)

# Config to control enhancement (can be toggled)
config = {
    "enhance_heightmap": True,
    "enhancement": {
        "z_curve_power": 0.9,          # Adjust Z-curve power
        "flatten_background": True,    # Enable background suppression
        "background_cutoff": 0.05,      # Adjust cutoff for background flattening
        "blur_sigma": 0.3,             # Apply Gaussian blur with sigma=1
        "edge_boost": False,           # Disable edge boosting
        "edge_boost_weight": 0.025,       #Subtle featuer/crisp boost
        "z_scale_mm": 0.0,             # Scale depth to 2.5mm
        "auto_normalize": True
    }
}

# Run test with your image
if __name__ == "__main__":
    image_path = "output/flamingo/image.png"  # Set your test image path here
    test_enhancement(image_path, config)
