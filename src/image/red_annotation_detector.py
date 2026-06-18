"""Detect red annotation regions in rendered plan PNG images."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None


def detect_red_regions(
    image: str | Path | Image.Image,
    min_area_px: int = 250,
) -> tuple[list[dict[str, Any]], Image.Image]:
    """Return red annotation regions and a debug mask image.

    The detector uses HSV thresholding with two red hue ranges, then applies a
    small binary dilation to connect thin red markup strokes.
    """
    pil_image = _load_rgb_image(image)
    rgb = np.asarray(pil_image)
    red_mask = _red_hsv_mask_optimized(rgb)
    cleaned_mask = _dilate(red_mask, iterations=1)
    regions = _regions_from_mask(cleaned_mask, min_area_px=min_area_px, bbox_mask=red_mask)
    debug_mask = Image.fromarray((cleaned_mask.astype(np.uint8) * 255), mode="L")
    return regions, debug_mask


def save_red_debug_mask(mask: Image.Image, output_path: str | Path) -> None:
    """Save a red detection debug mask, creating parent folders if needed."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(output_path)


def _load_rgb_image(image: str | Path | Image.Image) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")

    with Image.open(image) as opened_image:
        return opened_image.convert("RGB")


def _red_hsv_mask_optimized(rgb: np.ndarray) -> np.ndarray:
    """Memory-optimized red HSV mask calculation without generating full HSV image.

    Equivalent to original HSV red masks but runs in-place with minimal memory allocation.
    """
    R = rgb[..., 0].astype(np.float32)
    diff_GB = np.abs(rgb[..., 1].astype(np.float32) - rgb[..., 2].astype(np.float32))
    min_GB = np.minimum(rgb[..., 1], rgb[..., 2]).astype(np.float32)

    delta = R - min_GB
    del min_GB

    # Red is the maximum channel
    red_is_max = (rgb[..., 0] >= rgb[..., 1]) & (rgb[..., 0] >= rgb[..., 2])

    # Value >= 0.25 (R >= 63.75)
    value_ok = R >= 63.75

    # Saturation >= 0.35 (delta >= 0.35 * R)
    sat_ok = delta >= 0.35 * R

    # Hue check: diff_GB <= 0.25 * delta
    hue_ok = diff_GB <= 0.25 * delta

    mask = red_is_max & value_ok & sat_ok & hue_ok
    return mask



def _dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    result = mask
    for _ in range(iterations):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        result = (
            padded[:-2, :-2]
            | padded[:-2, 1:-1]
            | padded[:-2, 2:]
            | padded[1:-1, :-2]
            | padded[1:-1, 1:-1]
            | padded[1:-1, 2:]
            | padded[2:, :-2]
            | padded[2:, 1:-1]
            | padded[2:, 2:]
        )

    return result


def _regions_from_mask(
    mask: np.ndarray,
    min_area_px: int,
    bbox_mask: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    height, width = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    regions = []

    for y in range(height):
        for x in range(width):
            if visited[y, x] or not mask[y, x]:
                continue

            component = _collect_component(mask, visited, x, y)
            region = _tighten_region_to_mask(component, bbox_mask) if bbox_mask is not None else component
            if region["area_px"] < min_area_px:
                continue

            regions.append(region)

    regions.sort(key=lambda region: (region["bbox_image"][1], region["bbox_image"][0]))
    return [_format_region(index + 1, region) for index, region in enumerate(regions)]


def _collect_component(
    mask: np.ndarray,
    visited: np.ndarray,
    start_x: int,
    start_y: int,
) -> dict[str, Any]:
    queue = deque([(start_x, start_y)])
    visited[start_y, start_x] = True
    min_x = max_x = start_x
    min_y = max_y = start_y
    area_px = 0

    while queue:
        x, y = queue.popleft()
        area_px += 1
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)

        for next_x, next_y in _neighbors(x, y, mask.shape[1], mask.shape[0]):
            if visited[next_y, next_x] or not mask[next_y, next_x]:
                continue

            visited[next_y, next_x] = True
            queue.append((next_x, next_y))

    return {
        "bbox_image": [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1],
        "area_px": area_px,
    }


def _tighten_region_to_mask(region: dict[str, Any], mask: np.ndarray) -> dict[str, Any]:
    x, y, width, height = region["bbox_image"]
    cropped_mask = mask[y : y + height, x : x + width]
    points = np.argwhere(cropped_mask)

    if len(points) == 0:
        return region

    min_y, min_x = points.min(axis=0)
    max_y, max_x = points.max(axis=0)
    return {
        "bbox_image": [
            int(x + min_x),
            int(y + min_y),
            int(max_x - min_x + 1),
            int(max_y - min_y + 1),
        ],
        "area_px": int(cropped_mask.sum()),
    }


def _neighbors(x: int, y: int, width: int, height: int):
    for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if 0 <= next_x < width and 0 <= next_y < height:
            yield next_x, next_y


def _format_region(region_number: int, region: dict[str, Any]) -> dict[str, Any]:
    return {
        "region_id": f"RED-{region_number:03d}",
        "bbox_image": region["bbox_image"],
        "area_px": region["area_px"],
        "source": "red_annotation",
    }
