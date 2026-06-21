from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def ensure_candidate_preview_crops(
    project_root: Path,
    plan_id: str,
    candidates: list[dict[str, Any]],
    padding_px: int = 80,
) -> bool:
    page_path = project_root / "data" / "pages" / f"{plan_id}.png"
    if not page_path.is_file() or not candidates:
        return False

    crops_dir = project_root / "outputs" / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(page_path) as opened_image:
        page_image = opened_image.convert("RGB")

    changed = False
    for candidate in candidates:
        bbox_image = candidate.get("bbox_image")
        candidate_id = candidate.get("candidate_id")
        if not candidate_id or not _is_valid_bbox(bbox_image):
            continue

        preview_path = crops_dir / f"{plan_id}_{candidate_id}_preview.png"
        if candidate.get("source") == "pdf_words" and not _bbox_contains_visible_ink(page_image, bbox_image):
            if candidate.get("crop_path") == str(preview_path):
                candidate["crop_path"] = None
                changed = True
            continue

        candidate_padding_px = _candidate_padding_px(candidate, padding_px)
        crop_bbox = _padded_bbox(
            bbox_image,
            image_width=page_image.width,
            image_height=page_image.height,
            padding_px=candidate_padding_px,
        )
        if crop_bbox is None:
            continue

        crop = page_image.crop(tuple(crop_bbox))
        _draw_candidate_box(crop, bbox_image, crop_bbox)
        crop.save(preview_path)

        candidate["crop_path"] = str(preview_path)
        changed = True

    return changed


def _bbox_contains_visible_ink(
    image: Image.Image,
    bbox_image: list[int | float] | tuple[int | float, ...],
) -> bool:
    crop_bbox = _padded_bbox(
        bbox_image,
        image_width=image.width,
        image_height=image.height,
        padding_px=0,
    )
    if crop_bbox is None:
        return False

    crop = image.crop(tuple(crop_bbox)).convert("L")
    pixels = list(crop.getdata())
    if not pixels:
        return False

    dark_pixels = sum(1 for pixel in pixels if pixel < 180)
    return dark_pixels / len(pixels) >= 0.005


def _candidate_padding_px(candidate: dict[str, Any], default_padding_px: int) -> int:
    if candidate.get("source") == "pdf_words":
        return max(default_padding_px, 600)

    return default_padding_px


def _draw_candidate_box(
    crop: Image.Image,
    bbox_image: list[int | float] | tuple[int | float, ...],
    crop_bbox: list[int],
) -> None:
    x, y, width, height = [int(round(value)) for value in bbox_image]
    crop_x0, crop_y0, _, _ = crop_bbox
    rectangle = [
        x - crop_x0,
        y - crop_y0,
        x + width - crop_x0,
        y + height - crop_y0,
    ]
    ImageDraw.Draw(crop).rectangle(rectangle, outline=(255, 0, 0), width=5)


def _is_valid_bbox(bbox_image: Any) -> bool:
    return (
        isinstance(bbox_image, (list, tuple))
        and len(bbox_image) == 4
        and all(isinstance(value, (int, float)) for value in bbox_image)
        and bbox_image[2] > 0
        and bbox_image[3] > 0
    )


def _padded_bbox(
    bbox_image: list[int | float] | tuple[int | float, ...],
    image_width: int,
    image_height: int,
    padding_px: int,
) -> list[int] | None:
    if image_width <= 0 or image_height <= 0:
        return None

    x, y, width, height = [int(round(value)) for value in bbox_image]
    x0 = max(0, min(image_width - 1, x - padding_px))
    y0 = max(0, min(image_height - 1, y - padding_px))
    x1 = min(image_width, max(x0 + 1, x + width + padding_px))
    y1 = min(image_height, max(y0 + 1, y + height + padding_px))
    return [x0, y0, x1, y1]
