import logging
import json
from pathlib import Path
from typing import Any
from src.candidates.opening_label_parser import parse_opening_label, normalize_ocr_text
from src.candidates.pdf_words_candidate_extractor import extract_candidates_from_words
from src.candidates.validation import compute_iou, is_center_inside
from src.image.red_annotation_detector import detect_red_regions, save_red_debug_mask
from src.image.crop_regions import crop_red_regions
from src.image.ocr_crops import run_ocr_on_crops
from src.config.plan_config import PlanConfig
from src.config.spatial_mapping import assign_candidate_spatial_fields

logger = logging.getLogger(__name__)

VALID_STATUSES = {"needs_review", "verified", "rejected", "duplicate_candidate"}


def validate_candidate(candidate: dict[str, Any]) -> None:
    """
    Validate that the candidate dictionary conforms to the schema and field types.
    Raises TypeError or ValueError if validation fails.
    """
    if not isinstance(candidate.get("candidate_id"), str):
        raise TypeError(f"candidate_id must be a string, got {type(candidate.get('candidate_id'))}")
        
    if not isinstance(candidate.get("source"), str):
        raise TypeError(f"source must be a string, got {type(candidate.get('source'))}")
        
    label_type = candidate.get("label_type")
    if label_type is not None and not isinstance(label_type, str):
        raise TypeError(f"label_type must be a string or None, got {type(label_type)}")
        
    if not isinstance(candidate.get("raw_text"), str):
        raise TypeError(f"raw_text must be a string, got {type(candidate.get('raw_text'))}")
        
    norm_text = candidate.get("normalized_text")
    if norm_text is not None and not isinstance(norm_text, str):
        raise TypeError(f"normalized_text must be a string or None, got {type(norm_text)}")
        
    bbox = candidate.get("bbox_image")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise TypeError(f"bbox_image must be a list or tuple of 4 elements, got {type(bbox)}")
    for val in bbox:
        if not isinstance(val, (int, float)):
            raise TypeError(f"bbox_image elements must be numeric, got {type(val)}")
            
    crop_path = candidate.get("crop_path")
    if crop_path is not None and not isinstance(crop_path, str):
        raise TypeError(f"crop_path must be a string or None, got {type(crop_path)}")
        
    for int_field in ("width_mm", "height_mm", "diameter_mm", "ra_value", "ok_value"):
        val = candidate.get(int_field)
        if val is not None and not isinstance(val, int):
            raise TypeError(f"{int_field} must be an integer or None, got {type(val)}")
            
    ref = candidate.get("reference")
    if ref is not None and not isinstance(ref, str):
        raise TypeError(f"reference must be a string or None, got {type(ref)}")
        
    conf = candidate.get("confidence")
    if not isinstance(conf, (int, float)):
        raise TypeError(f"confidence must be float or int, got {type(conf)}")
        
    status = candidate.get("status")
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got '{status}'")


def extract_candidates_from_png_data(
    crops_metadata: list[dict[str, Any]],
    ocr_results: list[dict[str, Any]] | None = None,
    default_status: str = "needs_review"
) -> list[dict[str, Any]]:
    """
    Combine red region metadata and OCR results into a list of opening candidates.
    """
    candidates = []
    
    # Build a lookup for OCR text by region_id
    ocr_lookup = {}
    if ocr_results:
        for item in ocr_results:
            rid = item.get("region_id")
            if rid:
                ocr_lookup[rid] = {
                    "text": item.get("ocr_text", ""),
                    "available": item.get("ocr_available", False)
                }
                
    for idx, crop in enumerate(crops_metadata):
        region_id = crop.get("region_id")
        bbox_image = crop.get("bbox_image")
        crop_path = crop.get("crop_path")
        
        # Determine OCR availability
        ocr_info = ocr_lookup.get(region_id) if region_id else None
        
        if ocr_info is None:
            # OCR missing or not run for this region
            raw_text = ""
            source = "png_red_annotation_region"
            confidence = 0.3
        else:
            raw_text = ocr_info["text"] if ocr_info["text"] else ""
            raw_text_stripped = raw_text.strip()
            
            if not ocr_info["available"]:
                source = "png_red_annotation_region"
                confidence = 0.3
                raw_text = ""
            else:
                source = "png_red_annotation_ocr"
                if not raw_text_stripped:
                    confidence = 0.3
                    raw_text = ""
                else:
                    confidence = 0.5  # default if not parseable
                    raw_text = raw_text_stripped
                    
        # Defaults for parser fields
        label_type = None
        width_mm = None
        height_mm = None
        diameter_mm = None
        ra_value = None
        ok_value = None
        reference = None
        
        # Try to parse if we have OCR text
        normalized_text = None
        if raw_text:
            normalized_text = normalize_ocr_text(raw_text)
            parsed = parse_opening_label(normalized_text)
            if parsed:
                label_type = parsed.get("label_type")
                width_mm = parsed.get("width_mm")
                height_mm = parsed.get("height_mm")
                diameter_mm = parsed.get("diameter_mm")
                ra_value = parsed.get("ra_value")
                ok_value = parsed.get("ok_value")
                reference = parsed.get("reference")
                
        # Compute confidence score dynamically
        if not label_type:
            if not raw_text.strip():
                confidence = 0.20
            else:
                confidence = 0.30
        else:
            has_dim = (width_mm is not None) or (height_mm is not None) or (diameter_mm is not None)
            has_vertical = (ra_value is not None) or (ok_value is not None)
            has_ref = reference is not None
            
            if has_dim and has_vertical and has_ref:
                confidence = 0.90
            elif has_vertical and has_ref:
                confidence = 0.85
            elif has_dim:
                confidence = 0.75
            else:
                confidence = 0.60
                
        candidate = {
            "candidate_id": f"OP-{idx+1:03d}",
            "source": source,
            "label_type": label_type,
            "raw_text": raw_text,
            "normalized_text": normalized_text,
            "bbox_image": bbox_image,
            "crop_path": crop_path,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "diameter_mm": diameter_mm,
            "ra_value": ra_value,
            "ok_value": ok_value,
            "reference": reference,
            "confidence": confidence,
            "status": default_status
        }
        
        validate_candidate(candidate)
        candidates.append(candidate)
        
    return candidates


def run_png_extraction_pipeline(
    image_path: str | Path,
    plan_id: str,
    output_root: str | Path,
    padding_px: int = 80,
    min_area_px: int = 250,
    psm: int = 6,
    default_status: str = "needs_review",
    clean_red: bool = False,
    project_root: str | Path | None = None,
    words_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Orchestrate the end-to-end PNG extraction pipeline.
    """
    image_path = Path(image_path).resolve()
    output_root = Path(output_root).resolve()
    
    debug_dir = output_root / "debug"
    crops_dir = output_root / "crops"
    candidates_dir = output_root / "candidates"
    
    # Ensure all directories exist
    debug_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)
    candidates_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Detect red regions
    regions, debug_mask = detect_red_regions(image_path, min_area_px=min_area_px)
    mask_path = debug_dir / f"{plan_id}_red_mask.png"
    save_red_debug_mask(debug_mask, mask_path)
    
    crops_metadata_path = debug_dir / f"{plan_id}_red_crops.json"
    ocr_results_path = debug_dir / f"{plan_id}_ocr_results.json"
    candidates_path = candidates_dir / f"{plan_id}_candidates.json"
    config_root = Path(project_root).resolve() if project_root else output_root.parent
    resolved_words_path = (
        Path(words_path)
        if words_path is not None
        else config_root / "data" / "words" / f"{plan_id}_words.json"
    )
    word_candidates = _load_word_candidates(resolved_words_path)
    
    # 2. Check if no red regions are detected
    if not regions:
        # Save empty files
        with open(crops_metadata_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
            
        with open(ocr_results_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
            
        assign_candidate_spatial_fields(
            word_candidates,
            PlanConfig.load_for_plan(config_root, plan_id),
        )
        payload = {
            "plan_id": plan_id,
            "candidate_count": len(word_candidates),
            "candidates": word_candidates,
        }
        with open(candidates_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            
        return word_candidates
        
    # 3. Crop red regions
    crop_metadata = crop_red_regions(
        image=image_path,
        regions=regions,
        output_dir=crops_dir,
        plan_id=plan_id,
        padding_px=padding_px
    )
    with open(crops_metadata_path, "w", encoding="utf-8") as f:
        json.dump(crop_metadata, f, indent=2)
        
    # 4. OCR on crops
    ocr_results = run_ocr_on_crops(crop_metadata, psm=psm, clean_red=clean_red, output_root=output_root)
    with open(ocr_results_path, "w", encoding="utf-8") as f:
        json.dump(ocr_results, f, indent=2)
        
    # 5. Extract candidates
    candidates = extract_candidates_from_png_data(
        crops_metadata=crop_metadata,
        ocr_results=ocr_results,
        default_status=default_status
    )
    candidates = _merge_candidate_sources(word_candidates, candidates)
    assign_candidate_spatial_fields(candidates, PlanConfig.load_for_plan(config_root, plan_id))
    
    # 6. Validate candidates
    for c in candidates:
        validate_candidate(c)
        
    # 7. Save candidates
    payload = {
        "plan_id": plan_id,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return candidates


def _load_word_candidates(words_path: str | Path | None) -> list[dict[str, Any]]:
    if words_path is None:
        return []

    resolved_path = Path(words_path)
    if not resolved_path.is_file():
        return []

    words = json.loads(resolved_path.read_text(encoding="utf-8"))
    return extract_candidates_from_words(words)


def _merge_candidate_sources(
    word_candidates: list[dict[str, Any]],
    ocr_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not word_candidates:
        return ocr_candidates

    merged = [dict(candidate) for candidate in word_candidates]
    for ocr_candidate in ocr_candidates:
        overlapping_word = next(
            (
                candidate
                for candidate in merged
                if _candidate_boxes_overlap(candidate, ocr_candidate)
            ),
            None,
        )
        if overlapping_word is not None:
            if not overlapping_word.get("crop_path") and ocr_candidate.get("crop_path"):
                overlapping_word["crop_path"] = ocr_candidate["crop_path"]
            continue
        merged.append(dict(ocr_candidate))

    for index, candidate in enumerate(merged, start=1):
        candidate["candidate_id"] = f"OP-{index:03d}"
    return merged


def _candidate_boxes_overlap(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_bbox = first.get("bbox_image")
    second_bbox = second.get("bbox_image")
    if not first_bbox or not second_bbox:
        return False
    return (
        compute_iou(first_bbox, second_bbox) >= 0.05
        or is_center_inside(first_bbox, second_bbox)
        or is_center_inside(second_bbox, first_bbox)
    )
