"""Crop image context around detected red annotation regions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image
Image.MAX_IMAGE_PIXELS = None


def crop_red_regions(
    image: str | Path | Image.Image,
    regions: list[dict[str, Any]],
    output_dir: str | Path,
    plan_id: str,
    padding_px: int = 80,
) -> list[dict[str, Any]]:
    """Save padded crops for detected red regions and return crop metadata."""
    pil_image = _load_rgb_image(image)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = []

    for region in regions:
        crop_bbox = _padded_bbox(
            region["bbox_image"],
            image_width=pil_image.width,
            image_height=pil_image.height,
            padding_px=padding_px,
        )
        crop = pil_image.crop(tuple(crop_bbox))
        crop_path = output_dir / f"{plan_id}_{region['region_id']}.png"
        crop.save(crop_path)
        metadata.append(
            {
                "region_id": region["region_id"],
                "crop_path": str(crop_path),
                "bbox_image": region["bbox_image"],
                "crop_bbox_image": crop_bbox,
            }
        )

    return metadata


def _load_rgb_image(image: str | Path | Image.Image) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")

    with Image.open(image) as opened_image:
        return opened_image.convert("RGB")


def _padded_bbox(
    bbox_image: list[int],
    image_width: int,
    image_height: int,
    padding_px: int,
) -> list[int]:
    x, y, width, height = bbox_image
    x0 = max(0, x - padding_px)
    y0 = max(0, y - padding_px)
    x1 = min(image_width, x + width + padding_px)
    y1 = min(image_height, y + height + padding_px)
    return [x0, y0, x1, y1]
