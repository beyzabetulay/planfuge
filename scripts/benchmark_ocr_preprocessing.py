#!/usr/bin/env python3
"""Run OCR preprocessing benchmarking against real hard crop examples."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

from src.candidates.opening_label_parser import parse_opening_label
from src.image.ocr_crops import check_tesseract_availability


def apply_baseline(img: Image.Image) -> Image.Image:
    return img.convert("L")


def apply_red_cleanup(img: Image.Image) -> Image.Image:
    try:
        from src.image.red_cleanup import remove_red_pixels
        cleaned_img, _ = remove_red_pixels(img, dilation_iterations=1)
        return cleaned_img.convert("L")
    except Exception as e:
        print(f"Warning: Red cleanup failed, falling back to original image: {e}", file=sys.stderr)
        return img.convert("L")


def apply_resize_2x(img: Image.Image) -> Image.Image:
    resampling_filter = getattr(Image, "Resampling", Image).LANCZOS
    new_size = (img.width * 2, img.height * 2)
    return img.resize(new_size, resampling_filter).convert("L")


def apply_threshold(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    arr = np.asarray(gray)
    # Binary threshold at 127
    thresh_arr = np.where(arr > 127, 255, 0).astype(np.uint8)
    return Image.fromarray(thresh_arr, mode="L")


def apply_sharpen(img: Image.Image) -> Image.Image:
    return img.convert("L").filter(ImageFilter.SHARPEN)


PREPROCESSING_STRATEGIES = {
    "baseline_grayscale_psm6": apply_baseline,
    "red_cleanup": apply_red_cleanup,
    "resize_2x": apply_resize_2x,
    "threshold": apply_threshold,
    "sharpen": apply_sharpen,
}


def run_tesseract(img_gray: Image.Image, psm: int = 6) -> str:
    if not PYTESSERACT_AVAILABLE or not check_tesseract_availability():
        return ""
    
    config_str = f"--psm {psm}"
    # try deu+eng
    try:
        return pytesseract.image_to_string(img_gray, lang="deu+eng", config=config_str, timeout=5)
    except Exception:
        # try eng
        try:
            return pytesseract.image_to_string(img_gray, lang="eng", config=config_str, timeout=5)
        except Exception:
            # try default
            try:
                return pytesseract.image_to_string(img_gray, config=config_str, timeout=5)
            except Exception as e:
                print(f"Error running Tesseract: {e}", file=sys.stderr)
                return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark-dir",
        default="data/ocr_benchmark",
        help="Path to the benchmark folder. Defaults to data/ocr_benchmark."
    )
    parser.add_argument(
        "--out",
        default="outputs/debug/ocr_benchmark_report.json",
        help="Path to save the JSON report. Defaults to outputs/debug/ocr_benchmark_report.json."
    )
    args = parser.parse_args()

    benchmark_dir = Path(args.benchmark_dir)
    expected_json_path = benchmark_dir / "expected.json"
    crops_dir = benchmark_dir / "crops"
    report_output_path = Path(args.out)

    if not benchmark_dir.exists():
        print(f"Error: Benchmark directory not found at {benchmark_dir}", file=sys.stderr)
        sys.exit(1)

    if not expected_json_path.exists():
        print(f"Error: expected.json not found at {expected_json_path}", file=sys.stderr)
        sys.exit(1)

    if not crops_dir.exists():
        print(f"Error: crops directory not found at {crops_dir}", file=sys.stderr)
        sys.exit(1)

    # Load targets
    with open(expected_json_path, "r", encoding="utf-8") as f:
        expected_data = json.load(f)

    print(f"OCR Regression Benchmark for Hard Crops")
    print(f"Benchmark Dir: {benchmark_dir}")
    print(f"Output Report: {report_output_path}")
    print(f"Loaded {len(expected_data)} target crops.")

    # Initialize results structures
    summary_stats = {}
    detailed_results = {}

    for method_name in PREPROCESSING_STRATEGIES.keys():
        summary_stats[method_name] = {
            "expected_token_hits": 0,
            "total_expected_tokens": 0,
            "critical_errors": 0,
            "parser_successes": 0,
        }
        detailed_results[method_name] = {}

    # Run Benchmark
    for crop_filename, targets in expected_data.items():
        crop_path = crops_dir / crop_filename
        if not crop_path.exists():
            print(f"Warning: Crop image {crop_filename} not found in {crops_dir}", file=sys.stderr)
            continue

        expected_tokens = targets.get("expected_tokens", [])
        must_not_contain = targets.get("must_not_contain", [])

        # Load original image
        try:
            with Image.open(crop_path) as img:
                img_rgb = img.convert("RGB")
                
                for method_name, apply_fn in PREPROCESSING_STRATEGIES.items():
                    # Process image
                    processed_img_gray = apply_fn(img_rgb)
                    
                    # Run OCR
                    ocr_text = run_tesseract(processed_img_gray, psm=6)
                    ocr_text_clean = ocr_text.strip() if ocr_text else ""
                    ocr_text_upper = ocr_text_clean.upper().replace("\n", " ")

                    # Calculate token hits
                    hits = []
                    for t in expected_tokens:
                        if t.upper() in ocr_text_upper:
                            hits.append(t)
                    
                    # Calculate critical errors
                    errors_found = []
                    for t in must_not_contain:
                        if t.upper() in ocr_text_upper:
                            errors_found.append(t)

                    # Parse OCR text
                    parsed = parse_opening_label(ocr_text_clean)
                    parsed_label_type = parsed.get("label_type") if parsed else None
                    parsed_diameter_mm = parsed.get("diameter_mm") if parsed else None
                    parsed_ra_value = parsed.get("ra_value") if parsed else None
                    parsed_reference = parsed.get("reference") if parsed else None
                    parse_success = parsed is not None

                    # Record detailed details
                    detailed_results[method_name][crop_filename] = {
                        "ocr_text": ocr_text_clean,
                        "parsed_label_type": parsed_label_type,
                        "parsed_diameter_mm": parsed_diameter_mm,
                        "parsed_ra_value": parsed_ra_value,
                        "parsed_reference": parsed_reference,
                        "parse_success": parse_success,
                        "token_hits": hits,
                        "critical_errors_found": errors_found,
                    }

                    # Accumulate summary stats
                    stats = summary_stats[method_name]
                    stats["expected_token_hits"] += len(hits)
                    stats["total_expected_tokens"] += len(expected_tokens)
                    stats["critical_errors"] += len(errors_found)
                    if parse_success:
                        stats["parser_successes"] += 1

        except Exception as crop_err:
            print(f"Error processing crop {crop_filename}: {crop_err}", file=sys.stderr)

    # Print summary report
    print("\n" + "="*80)
    print("OCR BENCHMARK SUMMARY REPORT")
    print("="*80)
    header = f"{'Method':<30} | {'Token Hits':<12} | {'Critical Errors':<16} | {'Parser Success':<15}"
    print(header)
    print("-" * len(header))

    for method_name, stats in summary_stats.items():
        hits_str = f"{stats['expected_token_hits']}/{stats['total_expected_tokens']}"
        errors_str = f"{stats['critical_errors']}"
        success_str = f"{stats['parser_successes']}/{len(expected_data)}"
        print(f"{method_name:<30} | {hits_str:<12} | {errors_str:<16} | {success_str:<15}")

    # Build recommendations dynamically
    print("\n" + "="*80)
    print("RECOMMENDATIONS & REGRESSION EVALUATION")
    print("="*80)

    baseline_stats = summary_stats["baseline_grayscale_psm6"]
    
    recommendations = []
    for method_name, stats in summary_stats.items():
        if method_name == "baseline_grayscale_psm6":
            continue

        # Check if the method degrades any baseline performance metrics
        degrades_hits = stats["expected_token_hits"] < baseline_stats["expected_token_hits"]
        degrades_errors = stats["critical_errors"] > baseline_stats["critical_errors"]
        degrades_success = stats["parser_successes"] < baseline_stats["parser_successes"]

        improves_hits = stats["expected_token_hits"] > baseline_stats["expected_token_hits"]
        improves_success = stats["parser_successes"] > baseline_stats["parser_successes"]

        if degrades_hits or degrades_errors or degrades_success:
            issues = []
            if degrades_hits:
                issues.append("lower expected token hits")
            if degrades_errors:
                issues.append("higher critical error count")
            if degrades_success:
                issues.append("fewer parser successes")
            recommendations.append(
                f"- [DEPRECATE] Do NOT use '{method_name}' as default. (Issues: {', '.join(issues)} compared to baseline)"
            )
        elif improves_hits or improves_success:
            improvements = []
            if improves_hits:
                improvements.append("higher token hit rate")
            if improves_success:
                improvements.append("more parser successes")
            recommendations.append(
                f"- [UPGRADE] Strongly consider '{method_name}'. (Improvements: {', '.join(improvements)} compared to baseline)"
            )
        else:
            recommendations.append(
                f"- [NO CHANGE] '{method_name}' is equivalent to baseline."
            )

    for rec in recommendations:
        print(rec)

    # Save JSON report
    report_data = {
        "summary": {
            "total_crops": len(expected_data),
            "methods": summary_stats,
        },
        "detailed_results": detailed_results,
    }

    report_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        
    print(f"\nSaved full benchmark report to: {report_output_path}")


if __name__ == "__main__":
    main()
