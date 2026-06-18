#!/usr/bin/env python3
"""Compare OCR and candidate extraction success before and after red markup cleanup."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.candidates.png_candidate_extractor import run_png_extraction_pipeline
from src.candidates.validation import compare_candidates_to_examples
from src.image.ocr_crops import check_tesseract_availability


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan-id",
        default="SP_U1_0003",
        help="Plan ID to compare. Defaults to SP_U1_0003."
    )
    parser.add_argument(
        "--image",
        help="Path to plan image. Defaults to data/pages/<plan_id>.png"
    )
    parser.add_argument(
        "--examples-json",
        help="Path to manual annotations JSON. Defaults to data/annotations/<plan_id>_examples.json"
    )
    parser.add_argument(
        "--out",
        default="outputs",
        help="Output root directory. Defaults to 'outputs'"
    )
    args = parser.parse_args()

    plan_id = args.plan_id
    image_path = Path(args.image) if args.image else REPO_ROOT / "data" / "pages" / f"{plan_id}.png"
    examples_path = Path(args.examples_json) if args.examples_json else REPO_ROOT / "data" / "annotations" / f"{plan_id}_examples.json"
    output_root = Path(args.out).resolve()

    if not image_path.exists():
        print(f"Error: Plan image not found at {image_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Comparing OCR and Parser success before/after red cleanup for {plan_id}...")
    print(f"Image: {image_path}")
    print(f"Examples JSON: {examples_path if examples_path.exists() else 'Not found'}")

    # Check Tesseract
    if not check_tesseract_availability():
        print("Error: Tesseract is not available in PATH. Cannot perform comparison.", file=sys.stderr)
        sys.exit(1)

    # We run baseline in a temp directory to avoid overwriting outputs/candidates/SP_U1_0003_candidates.json
    with tempfile.TemporaryDirectory() as tmp_dir:
        baseline_out = Path(tmp_dir) / "baseline"
        
        print("\n--- Running Baseline (clean_red=False) ---")
        baseline_candidates = run_png_extraction_pipeline(
            image_path=image_path,
            plan_id=plan_id,
            output_root=baseline_out,
            clean_red=False
        )

        print("\n--- Running Cleaned (clean_red=True) ---")
        cleaned_candidates = run_png_extraction_pipeline(
            image_path=image_path,
            plan_id=plan_id,
            output_root=output_root,
            clean_red=True
        )

    # Let's align candidates by candidate_id for easy side-by-side comparison
    baseline_map = {c["candidate_id"]: c for c in baseline_candidates}
    cleaned_map = {c["candidate_id"]: c for c in cleaned_candidates}

    # Load examples if present
    examples = []
    if examples_path.exists():
        with open(examples_path, "r", encoding="utf-8") as f:
            examples = json.load(f)

    # Calculate validation metrics if examples exist
    baseline_metrics = None
    cleaned_metrics = None
    if examples:
        baseline_report = compare_candidates_to_examples(baseline_candidates, examples)
        cleaned_report = compare_candidates_to_examples(cleaned_candidates, examples)
        
        total_relevant = sum(1 for ex in examples if ex.get("is_opening_relevant", True))
        
        b_matched_relevant = len(baseline_report["matched_relevant"])
        b_recall = b_matched_relevant / total_relevant if total_relevant > 0 else 0.0
        
        c_matched_relevant = len(cleaned_report["matched_relevant"])
        c_recall = c_matched_relevant / total_relevant if total_relevant > 0 else 0.0
        
        baseline_metrics = {
            "recall": b_recall,
            "matched_relevant": b_matched_relevant,
            "total_relevant": total_relevant,
            "report": baseline_report
        }
        cleaned_metrics = {
            "recall": c_recall,
            "matched_relevant": c_matched_relevant,
            "total_relevant": total_relevant,
            "report": cleaned_report
        }

    # Compile side-by-side report
    print("\n" + "="*95)
    print("DETAILED SIDE-BY-SIDE OCR COMPARISON")
    print("="*95)
    
    header = f"{'Cand ID':<9} | {'Baseline Raw OCR Text':<35} | {'Cleaned Raw OCR Text':<35} | {'Parsed':<10}"
    print(header)
    print("-" * len(header))

    baseline_parsed_count = 0
    cleaned_parsed_count = 0

    for cand_id in sorted(baseline_map.keys()):
        bc = baseline_map[cand_id]
        cc = cleaned_map.get(cand_id, {})
        
        b_text = bc.get("raw_text", "").replace("\n", " ")
        c_text = cc.get("raw_text", "").replace("\n", " ")
        
        # Max length display
        if len(b_text) > 33:
            b_text = b_text[:30] + "..."
        if len(c_text) > 33:
            c_text = c_text[:30] + "..."
            
        b_parsed = bc.get("label_type") is not None
        c_parsed = cc.get("label_type") is not None
        
        if b_parsed:
            baseline_parsed_count += 1
        if c_parsed:
            cleaned_parsed_count += 1
            
        parsed_status = "No Change"
        if b_parsed and not c_parsed:
            parsed_status = "B only"
        elif not b_parsed and c_parsed:
            parsed_status = "C ONLY (*)"
        elif b_parsed and c_parsed:
            parsed_status = "Both"

        print(f"{cand_id:<9} | {b_text:<35} | {c_text:<35} | {parsed_status:<10}")

    print("="*95)
    print("SUMMARY METRICS TABLE")
    print("="*95)
    print(f"{'Metric':<40} | {'Baseline':<15} | {'Cleaned':<15}")
    print("-" * 76)
    print(f"{'Total Detections / Crops':<40} | {len(baseline_candidates):<15} | {len(cleaned_candidates):<15}")
    print(f"{'Parser Success Count':<40} | {baseline_parsed_count:<15} | {cleaned_parsed_count:<15}")
    
    if examples:
        print(f"{'Relevant Examples Recalled':<40} | {baseline_metrics['matched_relevant']}/{baseline_metrics['total_relevant']} ({baseline_metrics['recall']:.2%}) | {cleaned_metrics['matched_relevant']}/{cleaned_metrics['total_relevant']} ({cleaned_metrics['recall']:.2%})")

    # Target cases check
    print("\n" + "="*95)
    print("TARGETED INVESTIGATION: 'RA-65' and 'HSI150' cases")
    print("="*95)
    
    found_target = False
    for cand_id, cc in cleaned_map.items():
        bc = baseline_map[cand_id]
        b_text = bc.get("raw_text", "")
        c_text = cc.get("raw_text", "")
        
        # Check if either baseline or cleaned has RA or HSI
        if any(term in b_text or term in c_text for term in ["RA", "HSI", "RAS", "150", "190", "65"]):
            found_target = True
            print(f"Candidate {cand_id}:")
            print(f"  [Baseline] Raw OCR: '{b_text.strip()}' -> Parsed: {bc.get('label_type')} (Width: {bc.get('width_mm')}, Height: {bc.get('height_mm')}, Reference: {bc.get('reference')}, RA: {bc.get('ra_value')})")
            print(f"  [Cleaned]  Raw OCR: '{c_text.strip()}' -> Parsed: {cc.get('label_type')} (Width: {cc.get('width_mm')}, Height: {cc.get('height_mm')}, Reference: {cc.get('reference')}, RA: {cc.get('ra_value')})")
            print()
            
    if not found_target:
        print("No candidates matching target terms found.")


if __name__ == "__main__":
    main()
