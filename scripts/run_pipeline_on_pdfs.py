#!/usr/bin/env python3
"""Convert PDFs in target folder to PNGs and run candidate extraction pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add REPO_ROOT to path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF (fitz) is not installed. Please install it first.", file=sys.stderr)
    sys.exit(1)

from src.candidates.png_candidate_extractor import run_png_extraction_pipeline
from server.app.models import Opening, WeightConfig, GEOMETRY_ROUND, GEOMETRY_RECTANGULAR
from server.app.services.csv_export import serialize_csv, to_csv_row
from src.config.plan_config import PlanConfig


def parse_floor(plan_id: str) -> str:
    # E.g., SP_U1_0005 -> U1
    parts = plan_id.split("_")
    for part in parts:
        if part.startswith("U") and len(part) > 1 and part[1:].isdigit():
            return part
        if part.startswith("EG") or part.startswith("OG") or part.startswith("DG"):
            return part
    return "unknown"


def compute_grid_coordinate(x: float, y: float, plan_config: PlanConfig) -> str:
    if not plan_config.grid_anchors:
        return "grid_unknown"
        
    anchors = plan_config.grid_anchors
    tl_pix = anchors.get("top_left_pixel")
    tl_coord = anchors.get("top_left_coord")
    br_pix = anchors.get("bottom_right_pixel")
    br_coord = anchors.get("bottom_right_coord")
    
    if not (tl_pix and tl_coord and br_pix and br_coord):
        return "grid_unknown"
        
    try:
        def parse_coord(coord_str: str) -> tuple[int, int]:
            parts = coord_str.split("-")
            letter = parts[0].upper()
            number = int(parts[1])
            letter_idx = ord(letter) - ord("A")
            return letter_idx, number
            
        tl_l_idx, tl_n = parse_coord(tl_coord)
        br_l_idx, br_n = parse_coord(br_coord)
        
        dx_pix = br_pix[0] - tl_pix[0]
        dy_pix = br_pix[1] - tl_pix[1]
        
        if dx_pix == 0 or dy_pix == 0:
            return "grid_unknown"
            
        x_ratio = (x - tl_pix[0]) / dx_pix
        l_idx = int(round(tl_l_idx + x_ratio * (br_l_idx - tl_l_idx)))
        l_idx = max(0, min(25, l_idx))
        letter = chr(ord("A") + l_idx)
        
        y_ratio = (y - tl_pix[1]) / dy_pix
        n = int(round(tl_n + y_ratio * (br_n - tl_n)))
        n = max(1, min(100, n))
        
        return f"{letter}-{n}"
    except Exception:
        return "grid_unknown"


def candidate_to_opening(cand: dict, plan_id: str, plan_config: PlanConfig) -> Opening:
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

    # Calculate centroids
    bbox = cand.get("bbox_image", [0, 0, 0, 0])
    cx = bbox[0] + bbox[2] / 2
    cy = bbox[1] + bbox[3] / 2
    
    grid_coord = compute_grid_coordinate(cx, cy, plan_config)

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
        grid_coordinate=grid_coord,
        color_zone_id="zone_unknown",
        confidence=confidence,
        review_required=review_required,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf-dir",
        default=str(REPO_ROOT.parent / "pdf"),
        help="Path to the folder containing PDF files. Defaults to ../pdf."
    )
    parser.add_argument(
        "--out",
        default="outputs",
        help="Output root directory. Defaults to 'outputs'."
    )
    parser.add_argument(
        "--clean-red",
        action="store_true",
        default=True,
        help="Enable HSV-based red markup/cloud pixel cleanup. Defaults to True."
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir).resolve()
    output_root = Path(args.out).resolve()

    if not pdf_dir.exists() or not pdf_dir.is_dir():
        print(f"Error: PDF directory not found or is not a directory: {pdf_dir}", file=sys.stderr)
        sys.exit(1)

    pdf_files = sorted(list(pdf_dir.glob("*.pdf")))
    if not pdf_files:
        print(f"No PDF files found in {pdf_dir}", file=sys.stderr)
        sys.exit(0)

    print(f"Running pipeline on {len(pdf_files)} PDF files from {pdf_dir}")
    print(f"Output root: {output_root}")
    print(f"Clean red annotation markup: {args.clean_red}")

    # Create temporary or rendered directory for PNGs
    rendered_dir = output_root / "rendered"
    rendered_dir.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdf_files:
        plan_id = pdf_path.stem
        print(f"\nProcessing plan: {plan_id}...")

        # 1. Render PDF page 0 to PNG
        png_path = rendered_dir / f"{plan_id}.png"
        print(f"  Rendering {pdf_path.name} to {png_path.name} at 300 DPI...")
        try:
            doc = fitz.open(pdf_path)
            page = doc[0]
            mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)
            pix.save(png_path)
            doc.close()
            print(f"    Saved rendered PNG ({pix.width} x {pix.height} px)")
        except Exception as render_err:
            print(f"  Error rendering PDF {pdf_path.name}: {render_err}", file=sys.stderr)
            continue

        # 2. Run Candidate Extraction Pipeline
        print(f"  Running candidate extraction pipeline on {png_path.name}...")
        try:
            candidates = run_png_extraction_pipeline(
                image_path=png_path,
                plan_id=plan_id,
                output_root=output_root,
                clean_red=args.clean_red
            )
            print(f"    Extracted {len(candidates)} candidate(s).")
            candidates_path = output_root / "candidates" / f"{plan_id}_candidates.json"
            print(f"    Saved candidates to: {candidates_path}")

            # 3. Automatically export to final Contract CSV
            contract_dir = output_root / "contract_exports"
            contract_dir.mkdir(parents=True, exist_ok=True)
            csv_path = contract_dir / f"{plan_id}_contract.csv"

            plan_config = PlanConfig.load_for_plan(REPO_ROOT, plan_id)
            openings = [candidate_to_opening(cand, plan_id, plan_config) for cand in candidates]
            config = WeightConfig()
            rows = [to_csv_row(op, config) for op in openings]
            csv_content = serialize_csv(rows)
            csv_path.write_text(csv_content, encoding="utf-8")
            print(f"    Saved contract CSV to: {csv_path}")
        except Exception as e:
            print(f"  Error running extraction pipeline for {plan_id}: {e}", file=sys.stderr)

    print("\nAll PDFs processed successfully.")


if __name__ == "__main__":
    main()
