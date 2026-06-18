"""Convert PDF word-coordinate JSON into opening candidate JSON.

This module expects words that were already extracted from searchable PDFs.
It intentionally does not open PDF files, run OCR, or use the PNG pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.candidates.opening_label_parser import parse_opening_label

ANCHOR_PREFIXES = ("WDB", "DDB", "UZDB", "DDP")


def extract_candidates_json(
    words_path: str | Path,
    output_path: str | Path,
    plan_id: str | None = None,
) -> dict[str, Any]:
    """Load words JSON, extract candidates, and save candidate JSON."""
    words_path = Path(words_path)
    output_path = Path(output_path)
    words = json.loads(words_path.read_text(encoding="utf-8"))
    candidates = extract_candidates_from_words(words)
    result = {
        "plan_id": plan_id or _plan_id_from_words_path(words_path),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def extract_candidates_from_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract opening candidates from word-coordinate dictionaries."""
    normalized_words = [_normalize_word(word) for word in words]
    sorted_words = sorted(
        normalized_words,
        key=lambda word: (word["page"], word["y0"], word["x0"]),
    )
    candidates = []
    used_word_ids: set[int] = set()

    for index, word in enumerate(sorted_words):
        if index in used_word_ids or not _is_anchor(word["text"]):
            continue

        block_indices = _nearby_block_indices(sorted_words, index)
        block_words = [sorted_words[block_index] for block_index in block_indices]
        raw_text = " ".join(block_word["text"] for block_word in block_words)
        parsed = parse_opening_label(raw_text)

        if parsed is None:
            continue

        used_word_ids.update(block_indices)
        candidates.append(
            _candidate_from_block(len(candidates) + 1, raw_text, block_words, parsed)
        )

    return candidates


def _normalize_word(word: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": str(word.get("text", "")),
        "x0": float(word.get("x0", 0)),
        "y0": float(word.get("y0", 0)),
        "x1": float(word.get("x1", 0)),
        "y1": float(word.get("y1", 0)),
        "page": int(word.get("page", 1)),
    }


def _is_anchor(text: str) -> bool:
    upper_text = text.upper().replace("Р", "P")
    return upper_text.startswith(ANCHOR_PREFIXES) or "HSI" in upper_text


def _nearby_block_indices(
    words: list[dict[str, Any]],
    anchor_index: int,
    y_tolerance: float = 8.0,
    max_right_distance: float = 180.0,
) -> list[int]:
    anchor = words[anchor_index]
    anchor_center_y = _center_y(anchor)
    block_indices = []

    for index, word in enumerate(words):
        if word["page"] != anchor["page"]:
            continue
        if word["x0"] < anchor["x0"] - 2:
            continue
        if word["x0"] > anchor["x0"] + max_right_distance:
            continue
        if abs(_center_y(word) - anchor_center_y) > y_tolerance:
            continue

        block_indices.append(index)

    return sorted(block_indices, key=lambda index: words[index]["x0"])


def _candidate_from_block(
    candidate_number: int,
    raw_text: str,
    block_words: list[dict[str, Any]],
    parsed: dict[str, Any],
) -> dict[str, Any]:
    candidate = {
        "candidate_id": f"OP-{candidate_number:03d}",
        "source": "pdf_words",
        "raw_text": raw_text,
        "bbox_pdf": _union_bbox(block_words),
        "confidence": 0.85,
        "status": "needs_review",
    }
    candidate.update(parsed)
    return candidate


def _union_bbox(words: list[dict[str, Any]]) -> list[float]:
    return [
        min(word["x0"] for word in words),
        min(word["y0"] for word in words),
        max(word["x1"] for word in words),
        max(word["y1"] for word in words),
    ]


def _center_y(word: dict[str, Any]) -> float:
    return (word["y0"] + word["y1"]) / 2


def _plan_id_from_words_path(words_path: Path) -> str:
    suffix = "_words"
    stem = words_path.stem
    if stem.endswith(suffix):
        return stem[: -len(suffix)]

    return stem
