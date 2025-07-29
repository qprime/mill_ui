import numpy as np
import cv2


def enhance_heightmap(img_8bit: np.ndarray, config: dict) -> np.ndarray:
    """
    Process a grayscale 8-bit heightmap into an enhanced 16-bit depth map.
    Applies optional enhancement stages as defined in config['enhancement'].
    """
    # Step 1: 8-bit → 16-bit conversion
    img = np.uint16(img_8bit) * 257

    # Config namespace
    cfg = config.get('enhancement', {})

    # Step 2: Z-Curve Power Mapping
    power = cfg.get('z_curve_power', 1.0)
    if power != 1.0:
        img = z_curve(img, power)

    # Step 3: Background Suppression / Range Clamping
    if cfg.get('flatten_background', False):
        cutoff = cfg.get('background_cutoff', 0.2)
        img = flatten_background(img, cutoff)

    # Step 4: Gaussian Blur
    sigma = cfg.get('blur_sigma', 0.0)
    if sigma > 0.0:
        img = gaussian_blur(img, sigma)

    # Step 5: Edge Boost / Detail Injection
    if cfg.get('edge_boost', False):
        weight = cfg.get('edge_boost_weight', 0.3)
        img = edge_boost(img, weight)

    # Step 6: Optional auto-normalization
    if cfg.get('auto_normalize', False):
        img = normalize_16bit(img)

    return img

def normalize_16bit(img: np.ndarray) -> np.ndarray:
    """
    Normalize 16-bit image so full dynamic range [0, 65535] is used.
    """
    min_val = img.min()
    max_val = img.max()
    if max_val == min_val:
        return img  # avoid divide-by-zero
    norm = (img - min_val) / (max_val - min_val)
    return np.uint16(norm * 65535)


def z_curve(img: np.ndarray, power: float = 0.7) -> np.ndarray:
    norm = img / 65535.0
    remapped = np.clip(norm ** power, 0, 1)
    return np.uint16(remapped * 65535)


def flatten_background(img: np.ndarray, cutoff: float = 0.2) -> np.ndarray:
    norm = img / 65535.0
    flat = np.clip((norm - cutoff) / (1 - cutoff), 0, 1)
    return np.uint16(flat * 65535)


def gaussian_blur(img: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    ksize = max(3, int(6 * sigma) | 1)  # force odd kernel size
    return cv2.GaussianBlur(img, (ksize, ksize), sigmaX=sigma)


def edge_boost(img: np.ndarray, weight: float = 0.3) -> np.ndarray:
    """
    Apply a Laplacian-based edge boost to enhance contrast around edges.

    Args:
        img (np.ndarray): 16-bit input image (usually heightmap) as uint16.
        weight (float): Blend factor for how strongly to apply edge details.

    Returns:
        np.ndarray: Enhanced image, still in uint16 format.
    """
    img_f32 = img.astype(np.float32)
    laplacian = cv2.Laplacian(img_f32, cv2.CV_32F, ksize=3)
    boosted = img_f32 + (laplacian * weight)
    return np.clip(boosted, 0, 65535).astype(np.uint16)




def apply_z_scale(img: np.ndarray, z_scale_mm: float = -2.5) -> np.ndarray:
    return (img / 65535.0) * z_scale_mm
