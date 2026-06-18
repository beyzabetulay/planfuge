#!/usr/bin/env python3
"""Convert candidate JSON files to the ideal Riedel Bau contract CSV format."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add REPO_ROOT to path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.app.models import Opening, WeightConfig, GEOMETRY_ROUND, GEOMETRY_RECTANGULAR
from server.app.services.csv_export import serialize_csv, to_csv_row


def parse_floor(plan_id: str) -> str:
    # E.g., SP_U1_0005 -> U1
    parts = plan_id.split("_")
    for part in parts:
        if part.startswith("U") and len(part) > 1 and part[1:].isdigit():
            return part
        if part.startswith("EG") or part.startswith("OG") or part.startswith("DG"):
            return part
    return "unknown"


def candidate_to_opening(cand: dict, plan_id: str) -> Opening:
    diameter_mm = cand.get("diameter_mm")
    width_mm = cand.get("width_mm")
    height_mm = cand.get("height_mm")

    if diameter_mm is not None:
        geometry = GEOMETRY_ROUND
        length_cm = diameter_mm / 10.0
        width_cm = diameter_mm / 10.0
    else:
        geometry = GEOMETRY_RECTANGULAR
        length_cm = (width_mm / 10.0) if width_mm is not None else 0.0
        width_cm = (height_mm / 10.0) if height_mm is not None else 0.0

    # Default height_cm to 30 cm if not specified
    height_cm = 30.0

    label_type = cand.get("label_type")
    opening_type = "Ceiling" if label_type in ("WDB", "DDB") else "Unknown"

    floor = parse_floor(plan_id)
    confidence = cand.get("confidence", 0.5)
    status = cand.get("status", "needs_review")
    review_required = (status == "needs_review" or confidence < 0.7)

    return Opening(
        geometry=geometry,
        length_cm=length_cm,
        width_cm=width_cm,
        height_cm=height_cm,
        quantity=1,
        opening_type=opening_type,
        floor=floor,
        plan_name=plan_id,
        source_pdf=f"{plan_id}.pdf",
        grid_coordinate="grid_unknown",
        color_zone_id="zone_unknown",
        confidence=confidence,
        review_required=review_required,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates-json",
        required=True,
        help="Path to the candidates JSON file."
    )
    parser.add_argument(
        "--out-csv",
        required=True,
        help="Path to save the output CSV."
    )
    args = parser.parse_args()

    json_path = Path(args.candidates_json).resolve()
    csv_path = Path(args.out_csv).resolve()

    if not json_path.exists():
        print(f"Error: Candidate file {json_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # If it is a list or dictionary
    candidates = []
    plan_id = json_path.stem.replace("_candidates", "")
    
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        candidates = data.get("candidates", [])
        plan_id = data.get("plan_id", plan_id)

    openings = [candidate_to_opening(cand, plan_id) for cand in candidates]
    config = WeightConfig()
    rows = [to_csv_row(op, config) for op in openings]
    csv_content = serialize_csv(rows)

    try:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(csv_content, encoding="utf-8")
        print(f"Successfully exported {len(openings)} openings to {csv_path}")
    except Exception as e:
        print(f"Error writing CSV: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
