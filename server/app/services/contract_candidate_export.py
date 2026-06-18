from dataclasses import replace
from pathlib import Path

from server.app.models import GEOMETRY_RECTANGULAR, GEOMETRY_ROUND, Opening, WeightConfig
from server.app.services.csv_export import serialize_csv, to_csv_row
from src.config.plan_config import PlanConfig


def parse_floor(plan_id: str) -> str:
    parts = plan_id.split("_")
    for part in parts:
        if part.startswith("U") and len(part) > 1 and part[1:].isdigit():
            return part
        if part.startswith(("EG", "OG", "DG")):
            return part
    return "unknown"


def _point_in_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    inside = False
    previous = len(polygon) - 1
    for current in range(len(polygon)):
        current_y = polygon[current][1]
        previous_y = polygon[previous][1]
        if (current_y > y) != (previous_y > y):
            current_x = polygon[current][0]
            previous_x = polygon[previous][0]
            intersect_x = (previous_x - current_x) * (y - current_y) / (previous_y - current_y) + current_x
            if x < intersect_x:
                inside = not inside
        previous = current
    return inside


def _color_zone(x: float, y: float, plan_config: PlanConfig) -> str:
    for zone in plan_config.color_zones:
        polygon = zone.get("polygon")
        if polygon and _point_in_polygon(x, y, polygon):
            return zone.get("zone_id", "zone_unknown")
    return "zone_unknown"


def _nearest_label(positions: list, value: float) -> str | None:
    if not positions:
        return None
    pixels = [position[0] for position in positions]
    labels = [position[1] for position in positions]
    lo = 0
    hi = len(pixels) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if pixels[mid] <= value:
            lo = mid
        else:
            hi = mid - 1
    return labels[lo]


def _grid_coordinate(x: float, y: float, plan_config: PlanConfig) -> str:
    col_label = _nearest_label(plan_config.column_positions, x)
    row_label = _nearest_label(plan_config.row_positions, y)
    if col_label is not None and row_label is not None:
        return f"{col_label}-{row_label}"
    return "grid_unknown"


def candidate_to_opening(candidate: dict, plan_id: str, plan_config: PlanConfig) -> Opening:
    diameter_mm = candidate.get("diameter_mm")
    width_mm = candidate.get("width_mm")
    height_mm = candidate.get("height_mm")

    if diameter_mm is not None:
        geometry = GEOMETRY_ROUND
        length_cm = diameter_mm / 10.0
        width_cm = diameter_mm / 10.0
    else:
        geometry = GEOMETRY_RECTANGULAR
        length_cm = (width_mm / 10.0) if width_mm is not None else 0.0
        width_cm = (height_mm / 10.0) if height_mm is not None else 0.0

    label_type = candidate.get("label_type")
    opening_type = "Ceiling" if label_type in ("WDB", "DDB", "DDP") else "Unknown"
    confidence = candidate.get("confidence", 0.5)
    status = candidate.get("status", "needs_review")
    bbox = candidate.get("bbox_image") or [0, 0, 0, 0]
    center_x = bbox[0] + bbox[2] / 2
    center_y = bbox[1] + bbox[3] / 2

    uses_default_height = candidate.get("ra_value") is None and candidate.get("ok_value") is None
    review_required = status != "verified" or confidence < 0.60 or uses_default_height

    return Opening(
        geometry=geometry,
        length_cm=length_cm,
        width_cm=width_cm,
        height_cm=plan_config.default_height_cm,
        quantity=1,
        opening_type=opening_type,
        floor=parse_floor(plan_id),
        plan_name=plan_id,
        source_pdf=f"{plan_id}.pdf",
        grid_coordinate=_grid_coordinate(center_x, center_y, plan_config),
        color_zone_id=_color_zone(center_x, center_y, plan_config),
        confidence=confidence,
        review_required=review_required,
    )


def is_exportable_candidate(candidate: dict) -> bool:
    """Only final-export candidates with usable geometry dimensions."""
    if candidate.get("diameter_mm") is not None:
        return True
    return candidate.get("width_mm") is not None and candidate.get("height_mm") is not None


def group_openings(openings: list[Opening], candidates: list[dict], max_pixel_dist: float = 2000.0) -> list[Opening]:
    centroids = []
    for candidate in candidates:
        bbox = candidate.get("bbox_image") or [0, 0, 0, 0]
        centroids.append((bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2))

    grouped = []
    used = set()

    for index, opening in enumerate(openings):
        if index in used:
            continue

        quantity = 1
        used.add(index)

        for other_index in range(index + 1, len(openings)):
            if other_index in used:
                continue

            other = openings[other_index]
            if (
                opening.geometry != other.geometry
                or opening.length_cm != other.length_cm
                or opening.width_cm != other.width_cm
                or opening.height_cm != other.height_cm
                or opening.opening_type != other.opening_type
                or opening.grid_coordinate != other.grid_coordinate
            ):
                continue

            dx = centroids[index][0] - centroids[other_index][0]
            dy = centroids[index][1] - centroids[other_index][1]
            if (dx * dx + dy * dy) ** 0.5 > max_pixel_dist:
                continue

            quantity += 1
            used.add(other_index)

        grouped.append(replace(opening, quantity=quantity))

    return grouped


def export_contract_openings_csv(project_root: Path, plan_id: str, candidates: list[dict]) -> dict:
    exports_dir = project_root / "outputs" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    exportable_candidates = [candidate for candidate in candidates if is_exportable_candidate(candidate)]
    plan_config = PlanConfig.load_for_plan(project_root, plan_id)
    openings = [candidate_to_opening(candidate, plan_id, plan_config) for candidate in exportable_candidates]
    grouped_openings = group_openings(openings, exportable_candidates)
    rows = [to_csv_row(opening, WeightConfig()) for opening in grouped_openings]

    file_path = exports_dir / f"{plan_id}_verified_openings.csv"
    file_path.write_text(serialize_csv(rows), encoding="utf-8")

    return {
        "status": "success",
        "path": str(file_path.absolute()),
        "exported_count": len(grouped_openings),
    }
