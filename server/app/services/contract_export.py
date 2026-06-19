"""Generate the Riedel Bau contract-format CSV/JSON from candidate data."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path

from src.config.plan_config import PlanConfig

DENSITY_KG_M3 = 440.0
MAX_WEIGHT_KG = 25.0
MAX_GROUP_DISTANCE_PX = 2000.0
_HEIGHT_PAT = re.compile(r"d\s*=\s*(\d+)\s*cm", re.IGNORECASE)

CONTRACT_COLUMNS = [
    "Floor",
    "Construction phase/Plan name",
    "Length/cm",
    "Width/cm",
    "Height/cm",
    "Geometry",
    "Type",
    "Number",
    "Weight/kg",
    "Review status",
]


def _load_height_labels(project_root: Path, plan_id: str) -> list[dict]:
    path = project_root / "data" / "words" / f"{plan_id}_words.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        words = json.load(f)
    labels = []
    for w in words:
        m = _HEIGHT_PAT.search(w["text"])
        if m:
            cx = (w["x0"] + w["x1"]) / 2
            cy = (w["y0"] + w["y1"]) / 2
            labels.append({"height_cm": int(m.group(1)), "cx": cx, "cy": cy})
    return labels


def _nearest_height(
    bbox_pdf: list | None,
    labels: list[dict],
    default_height_cm: float,
) -> tuple[float, bool]:
    if not bbox_pdf or len(bbox_pdf) < 4 or not labels:
        return default_height_cm, True
    cx = (bbox_pdf[0] + bbox_pdf[2]) / 2
    cy = (bbox_pdf[1] + bbox_pdf[3]) / 2
    best_dist = float("inf")
    best_h = default_height_cm
    for h in labels:
        d = math.hypot(h["cx"] - cx, h["cy"] - cy)
        if d < best_dist:
            best_dist = d
            best_h = float(h["height_cm"])
    return best_h, False


def _volume_cm3(geometry: str, length_cm: float, width_cm: float, height_cm: float) -> float:
    if geometry == "round":
        return math.pi * (length_cm / 2) ** 2 * height_cm
    return length_cm * width_cm * height_cm


def _parse_floor(plan_id: str) -> str:
    for part in plan_id.split("_"):
        if part.startswith("U") and len(part) > 1 and part[1:].isdigit():
            return part
        if part[:2] in ("EG", "OG", "DG"):
            return part
    return "unknown"


def _opening_type(label_type: str | None) -> str:
    if label_type == "DDB":
        return "Ceiling"
    if label_type == "WDB":
        return "Wall"
    return "Unknown"


def _reviewable_candidates(candidates: list[dict]) -> list[dict]:
    return [
        candidate
        for candidate in candidates
        if candidate.get("status") not in {"rejected", "duplicate_candidate"}
    ]


def _candidate_center(candidate: dict) -> tuple[float, float] | None:
    bbox_image = candidate.get("bbox_image")
    if not bbox_image or len(bbox_image) < 4:
        return None
    return bbox_image[0] + bbox_image[2] / 2, bbox_image[1] + bbox_image[3] / 2


def _opening_group_key(opening: dict) -> tuple:
    return (
        opening["floor"],
        opening["plan_name"],
        opening["length_cm"],
        opening["width_cm"],
        opening["height_cm"],
        opening["geometry"],
        opening["opening_type"],
        opening["review_required"],
    )


def _build_rows(project_root: Path, plan_id: str, candidates: list[dict]) -> list[dict]:
    height_labels = _load_height_labels(project_root, plan_id)
    plan_config = PlanConfig.load_for_plan(project_root, plan_id)
    floor = _parse_floor(plan_id)

    openings: list[dict] = []
    for c in candidates:
        diameter_mm = c.get("diameter_mm")
        width_mm = c.get("width_mm")
        height_mm = c.get("height_mm")

        if diameter_mm is None and width_mm is None:
            continue

        if diameter_mm is not None:
            geometry = "round"
            length_cm = round(diameter_mm / 10.0, 1)
            width_cm = round(diameter_mm / 10.0, 1)
        else:
            geometry = "rectangular"
            length_cm = round((width_mm or 0) / 10.0, 1)
            width_cm = round((height_mm or 0) / 10.0, 1)

        height_cm, uses_default_height = _nearest_height(
            c.get("bbox_pdf"),
            height_labels,
            plan_config.default_height_cm,
        )
        o_type = _opening_type(c.get("label_type"))
        center = _candidate_center(c)

        openings.append({
            "floor": floor,
            "plan_name": plan_id,
            "length_cm": length_cm,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "geometry": geometry,
            "opening_type": o_type,
            "center": center,
            "review_required": (
                c.get("status") != "verified"
                or uses_default_height
                or c.get("confidence", 0.5) < 0.60
            ),
        })

    groups: list[dict] = []
    for o in openings:
        key = _opening_group_key(o)
        for group in groups:
            if group["key"] != key or o["center"] is None or group["center"] is None:
                continue
            if math.dist(o["center"], group["center"]) <= MAX_GROUP_DISTANCE_PX:
                group["count"] += 1
                break
        else:
            groups.append({"key": key, "center": o["center"], "count": 1})

    rows = []
    for group in groups:
        floor, plan_name, length_cm, width_cm, height_cm, geometry, o_type, review_required = group["key"]
        count = group["count"]
        vol = _volume_cm3(geometry, length_cm, width_cm, height_cm)
        weight_kg = round(vol / 1_000_000 * DENSITY_KG_M3 * count, 1)
        if weight_kg > MAX_WEIGHT_KG:
            status = "split_recommended"
        elif review_required:
            status = "review_required"
        else:
            status = "ready"
        rows.append({
            "Floor": floor,
            "Construction phase/Plan name": plan_name,
            "Length/cm": length_cm,
            "Width/cm": width_cm,
            "Height/cm": height_cm,
            "Geometry": geometry,
            "Type": o_type,
            "Number": count,
            "Weight/kg": weight_kg,
            "Review status": status,
        })

    return rows


def generate_contract_csv(project_root: Path, plan_id: str, candidates: list[dict]) -> bytes:
    """Return Excel-compatible UTF-8 BOM CSV bytes."""
    rows = _build_rows(project_root, plan_id, _reviewable_candidates(candidates))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CONTRACT_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def generate_contract_json(project_root: Path, plan_id: str, candidates: list[dict]) -> bytes:
    """Return JSON bytes of the contract-format openings."""
    rows = _build_rows(project_root, plan_id, _reviewable_candidates(candidates))
    payload = {
        "plan_id": plan_id,
        "opening_count": len(rows),
        "density_kg_per_m3": DENSITY_KG_M3,
        "max_weight_kg": MAX_WEIGHT_KG,
        "openings": rows,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
