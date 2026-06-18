"""Parse construction opening labels into structured candidate fields."""

from __future__ import annotations

import re
from typing import Any

LABEL_TYPES = ("UZDB", "WDB", "DDB", "DDP")
REFERENCES = ("UKRD", "OKRB", "UKRB")


def parse_opening_label(text: str) -> dict[str, Any] | None:
    """Parse a raw opening label string.

    Returns ``None`` when the text does not look like an opening label. Missing
    fields are returned as ``None`` so callers can safely serialize the result.
    """
    normalized = _normalize_text(text)
    label_type = _parse_label_type(normalized)
    diameter_mm = _parse_diameter(normalized)
    # An explicit separator (\ x l |) in the raw text strongly signals a dimension expression.
    # In that case, we allow dimension parsing even without a label prefix.
    has_explicit_separator = bool(re.search(r'\d\s*(?:\\|[xXlL\|])\s*\d', text))
    require_prefix = label_type is None and diameter_mm is None and not has_explicit_separator
    width_mm, height_mm = _parse_rectangular_dimensions(normalized, require_prefix=require_prefix)

    if label_type is None and width_mm is None and diameter_mm is None:
        return None

    return {
        "label_type": label_type,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "diameter_mm": diameter_mm,
        "ra_value": _parse_signed_value(normalized, "RA"),
        "ok_value": _parse_signed_value(normalized, "OK"),
        "reference": _parse_reference(normalized),
    }


def normalize_ocr_text(text: str) -> str:
    """Apply specific OCR normalization rules for opening labels."""
    normalized = text.upper()
    
    # 1. Normalize @ followed by digits to Ø: e.g. @15 -> Ø15, @25 -> Ø25
    normalized = re.sub(r'@\s*(\d{1,3})', r'Ø\1', normalized)
    
    # 2. Normalize rectangular dimension separators to '/' between digits (e.g. 65 \ 38 -> 65/38, 65 l 38 -> 65/38, 65x38 -> 65/38)
    normalized = re.sub(r'(\d{1,3})\s*(?:\\|X|L|\|)\s*(\d{1,3})', r'\1/\2', normalized)
    
    # Check if a label prefix is nearby (WDB, DDB, UZDB, DDP)
    has_prefix = any(p in normalized for p in ("WDB", "DDB", "UZDB", "DDP"))
    
    if has_prefix:
        # - "O15" -> "Ø15", "015" -> "Ø15", "025" -> "Ø25"
        normalized = re.sub(r'\b([O0])(15|25)\b', r'Ø\2', normalized)
        
        # - "DDB 916" -> "DDB Ø16"
        normalized = re.sub(r'\bDDB\s*916\b', 'DDB Ø16', normalized)
        
        # - "DDB Bio" -> "DDB Ø10"
        normalized = re.sub(r'\bDDB\s*BIO\b', 'DDB Ø10', normalized)
        
    return normalized


def _normalize_text(text: str) -> str:
    """Normalize common OCR/PDF text variants without changing meaning."""
    text = normalize_ocr_text(text)
    
    normalized = (
        text
        .replace("⌀", "Ø")
        .replace("Ф", "Ø")
        .replace("Р", "P")
    )
    return normalized


def _parse_label_type(text: str) -> str | None:
    for label_type in LABEL_TYPES:
        if re.search(rf"\b{label_type}\b|{label_type}\d", text):
            return label_type

    if re.search(r"\bHSI\s*\d+", text):
        return "HSI"

    return None


def _parse_rectangular_dimensions(text: str, require_prefix: bool = False) -> tuple[int | None, int | None]:
    # Require both sides to be at least 2 digits.
    # Not preceded/followed by a digit or decimal point (avoids matching 13.5/40 → 3/40).
    # Works for both spaced "WDB 40/20" and compact "DDB130/140" forms.
    pattern = r"(?<![\d.])(\d{2,3})\s*/\s*(\d{2,3})(?![\d.])"
    match = re.search(pattern, text)

    if not match:
        return None, None

    # If no label prefix is present, only extract dimensions when text has a known label type
    if require_prefix:
        has_label_nearby = any(p in text for p in ("WDB", "DDB", "UZDB", "DDP", "HSI"))
        if not has_label_nearby:
            return None, None

    width_cm, height_cm = (int(match.group(1)), int(match.group(2)))
    return width_cm * 10, height_cm * 10


def _parse_diameter(text: str) -> int | None:
    hsi_match = re.search(r"\bHSI\s*(\d{2,3})\b", text)
    if hsi_match:
        return int(hsi_match.group(1))

    diameter_match = re.search(r"Ø\s*(\d{1,3})\b", text)
    if not diameter_match:
        return None

    value = int(diameter_match.group(1))
    if value < 100:
        return value * 10

    return value


def _parse_signed_value(text: str, marker: str) -> int | None:
    match = re.search(rf"\b{marker}\s*([-+]?\d+)\b", text)
    if not match:
        return None

    return int(match.group(1))


def _parse_reference(text: str) -> str | None:
    for reference in REFERENCES:
        if re.search(rf"\b{reference}\b", text):
            return reference

    return None
