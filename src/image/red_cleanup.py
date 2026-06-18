import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
from src.image.red_annotation_detector import _red_hsv_mask_optimized, _dilate


def remove_red_pixels(pil_image: Image.Image, dilation_iterations: int = 1) -> tuple[Image.Image, Image.Image]:
    """
    Remove red annotation pixels from a PIL Image by replacing them with white pixels.
    Returns a tuple of (cleaned_pil_image, red_mask_pil_image).
    """
    rgb_img = pil_image.convert("RGB")
    rgb = np.asarray(rgb_img)
    red_mask = _red_hsv_mask_optimized(rgb)
    
    if dilation_iterations > 0:
        red_mask = _dilate(red_mask, iterations=dilation_iterations)
        
    # Replace mask pixels with white [255, 255, 255]
    cleaned_rgb = rgb.copy()
    cleaned_rgb[red_mask] = [255, 255, 255]
    
    cleaned_pil = Image.fromarray(cleaned_rgb, mode="RGB")
    mask_pil = Image.fromarray((red_mask.astype(np.uint8) * 255), mode="L")
    
    return cleaned_pil, mask_pil
