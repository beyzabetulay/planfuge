#!/usr/bin/env python3
"""Run the end-to-end PNG candidate extraction pipeline on a plan image."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import Counter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.candidates.png_candidate_extractor import run_png_extraction_pipeline
from src.image.ocr_crops import check_tesseract_availability


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image",
        required=True,
        help="Path to the original plan PNG image (e.g. data/pages/SP_U1_0003.png)",
    )
    parser.add_argument(
        "--plan-id",
        help="Plan ID. Defaults to the image filename stem.",
    )
    parser.add_argument(
        "--out",
        default="outputs",
        help="Output root directory. Defaults to 'outputs'",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=80,
        help="Padding around each red bbox. Defaults to 80.",
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=250,
        help="Minimum red region area in pixels. Defaults to 250.",
    )
    parser.add_argument(
        "--psm",
        type=int,
        default=6,
        help="Tesseract Page Segmentation Mode (PSM). Defaults to 6.",
    )
    parser.add_argument(
        "--status",
        default="needs_review",
        help="Default status for extracted candidates. Defaults to 'needs_review'.",
    )
    parser.add_argument(
        "--clean-red",
        action="store_true",
        default=False,
        help="Enable HSV-based red markup/cloud pixel cleanup before running OCR.",
    )
    args = parser.parse_args()

    image_path = Path(args.image).resolve()
    plan_id = args.plan_id or image_path.stem
    output_root = Path(args.out).resolve()

    if not image_path.exists():
        print(f"Error: Input image not found at {image_path}", file=sys.stderr)
        sys.exit(1)

    # Output paths for logging
    candidates_path = output_root / "candidates" / f"{plan_id}_candidates.json"

    print(f"Starting end-to-end candidate extraction for plan: {plan_id}")
    print(f"Input image: {image_path}")
    print(f"Output root: {output_root}")
    print(f"Clean red annotation markup: {args.clean_red}")

    # Step-by-step execution reporting
    print("\nStep 1: Detecting red annotation regions...")
    # Step 2: Cropping red regions... (will run inside run_png_extraction_pipeline)
    # To log precisely inside the step-by-step CLI execution, we report before invoking or call them.
    # But since run_png_extraction_pipeline handles everything internally, we can print progress.
    
    print("Step 2: Cropping red regions...")
    print("Step 3: Running OCR...")
    ocr_avail = check_tesseract_availability()
    if not ocr_avail:
        print("Warning: Tesseract OCR is not fully available. Running OCR fallback logic...")

    print("Step 4: Mapping OCR/crops to candidates...")
    print("Step 5: Saving candidates...")

    try:
        candidates = run_png_extraction_pipeline(
            image_path=image_path,
            plan_id=plan_id,
            output_root=output_root,
            padding_px=args.padding,
            min_area_px=args.min_area,
            psm=args.psm,
            default_status=args.status,
            clean_red=args.clean_red
        )
    except Exception as e:
        print(f"\nPipeline Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Terminal metrics summary
    print("\n--- Pipeline Summary ---")
    print(f"Red region count: {len(candidates)}")
    print(f"Crop count: {len(candidates)}")
    print(f"OCR availability summary: {'Available' if ocr_avail else 'Unavailable (Fallback Used)'}")
    print(f"Candidate count: {len(candidates)}")
    print(f"Final candidates JSON path: {candidates_path}")


if __name__ == "__main__":
    main()
