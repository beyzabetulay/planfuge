import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import json
from PIL import Image

from src.candidates.png_candidate_extractor import (
    extract_candidates_from_png_data, 
    validate_candidate,
    run_png_extraction_pipeline
)


class TestPngCandidateExtractor(unittest.TestCase):
    def setUp(self):
        self.crops_metadata = [
            {
                "region_id": "RED-001",
                "crop_path": "outputs/crops/SP_U1_0003_RED-001.png",
                "bbox_image": [10, 20, 30, 40],
                "crop_bbox_image": [0, 10, 40, 50]
            },
            {
                "region_id": "RED-002",
                "crop_path": "outputs/crops/SP_U1_0003_RED-002.png",
                "bbox_image": [100, 200, 50, 60],
                "crop_bbox_image": [90, 190, 70, 80]
            }
        ]

        self.ocr_results = [
            {
                "region_id": "RED-001",
                "crop_path": "outputs/crops/SP_U1_0003_RED-001.png",
                "ocr_text": "WDB 70/20 OK -60 UKRD",
                "ocr_available": True
            },
            {
                "region_id": "RED-002",
                "crop_path": "outputs/crops/SP_U1_0003_RED-002.png",
                "ocr_text": "Random Noise Text",
                "ocr_available": True
            }
        ]

    def test_extract_candidates_with_ocr(self):
        # RED-001 is parseable, RED-002 is unparseable
        candidates = extract_candidates_from_png_data(self.crops_metadata, self.ocr_results)

        self.assertEqual(len(candidates), 2)

        # RED-001 (parseable)
        c1 = candidates[0]
        self.assertEqual(c1["candidate_id"], "OP-001")
        self.assertEqual(c1["source"], "png_red_annotation_ocr")
        self.assertEqual(c1["label_type"], "WDB")
        self.assertEqual(c1["raw_text"], "WDB 70/20 OK -60 UKRD")
        self.assertEqual(c1["normalized_text"], "WDB 70/20 OK -60 UKRD")
        self.assertEqual(c1["bbox_image"], [10, 20, 30, 40])
        self.assertEqual(c1["width_mm"], 700)
        self.assertEqual(c1["height_mm"], 200)
        self.assertIsNone(c1["diameter_mm"])
        self.assertIsNone(c1["ra_value"])
        self.assertEqual(c1["ok_value"], -60)
        self.assertEqual(c1["reference"], "UKRD")
        self.assertEqual(c1["confidence"], 0.90)  # label_type + dim + vertical + ref
        self.assertEqual(c1["status"], "needs_review")

        # RED-002 (unparseable)
        c2 = candidates[1]
        self.assertEqual(c2["candidate_id"], "OP-002")
        self.assertEqual(c2["source"], "png_red_annotation_ocr")
        self.assertIsNone(c2["label_type"])
        self.assertEqual(c2["raw_text"], "Random Noise Text")
        self.assertEqual(c2["normalized_text"], "RANDOM NOISE TEXT")
        self.assertEqual(c2["bbox_image"], [100, 200, 50, 60])
        self.assertIsNone(c2["width_mm"])
        self.assertIsNone(c2["height_mm"])
        self.assertIsNone(c2["diameter_mm"])
        self.assertIsNone(c2["ra_value"])
        self.assertIsNone(c2["ok_value"])
        self.assertIsNone(c2["reference"])
        self.assertEqual(c2["confidence"], 0.30)  # label_type None, raw_text present
        self.assertEqual(c2["status"], "needs_review")

    def test_extract_candidates_missing_ocr_results(self):
        # If ocr_results is None
        candidates = extract_candidates_from_png_data(self.crops_metadata, ocr_results=None)

        self.assertEqual(len(candidates), 2)
        for i, c in enumerate(candidates):
            self.assertEqual(c["candidate_id"], f"OP-{i+1:03d}")
            self.assertEqual(c["source"], "png_red_annotation_region")
            self.assertIsNone(c["label_type"])
            self.assertEqual(c["raw_text"], "")
            self.assertIsNone(c["normalized_text"])
            self.assertEqual(c["confidence"], 0.20)  # label_type None, raw_text empty
            self.assertEqual(c["status"], "needs_review")

    def test_extract_candidates_empty_ocr_text(self):
        ocr_results_empty = [
            {
                "region_id": "RED-001",
                "crop_path": "outputs/crops/SP_U1_0003_RED-001.png",
                "ocr_text": "   ",
                "ocr_available": True
            }
        ]
        candidates = extract_candidates_from_png_data(self.crops_metadata[:1], ocr_results_empty)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c["raw_text"], "")
        self.assertIsNone(c["normalized_text"])
        self.assertEqual(c["confidence"], 0.20)  # label_type None, raw_text empty
        self.assertEqual(c["source"], "png_red_annotation_ocr")

    def test_validate_candidate_valid(self):
        valid_candidate = {
            "candidate_id": "OP-001",
            "source": "png_red_annotation_ocr",
            "label_type": "WDB",
            "raw_text": "WDB 70/20 OK -60 UKRD",
            "normalized_text": "WDB 70/20 OK -60 UKRD",
            "bbox_image": [10, 20, 30, 40],
            "crop_path": "outputs/crops/SP_U1_0003_RED-001.png",
            "width_mm": 700,
            "height_mm": 200,
            "diameter_mm": None,
            "ra_value": None,
            "ok_value": -60,
            "reference": "UKRD",
            "confidence": 0.90,
            "status": "needs_review"
        }
        # Should not raise any exception
        validate_candidate(valid_candidate)

    def test_validate_candidate_invalid_types(self):
        # Invalid bbox_image type (not list of 4 numbers)
        invalid_bbox = {
            "candidate_id": "OP-001",
            "source": "png_red_annotation_ocr",
            "label_type": None,
            "raw_text": "",
            "bbox_image": "10,20,30,40",
            "crop_path": None,
            "width_mm": None,
            "height_mm": None,
            "diameter_mm": None,
            "ra_value": None,
            "ok_value": None,
            "reference": None,
            "confidence": 0.3,
            "status": "needs_review"
        }
        with self.assertRaises((TypeError, ValueError)):
            validate_candidate(invalid_bbox)

        # Invalid width_mm type (should be int or None)
        invalid_width = invalid_bbox.copy()
        invalid_width["bbox_image"] = [10, 20, 30, 40]
        invalid_width["width_mm"] = "700"
        with self.assertRaises((TypeError, ValueError)):
            validate_candidate(invalid_width)

        # Invalid status value
        invalid_status = invalid_bbox.copy()
        invalid_status["bbox_image"] = [10, 20, 30, 40]
        invalid_status["status"] = "unknown_status"
        with self.assertRaises((TypeError, ValueError)):
            validate_candidate(invalid_status)

    @patch("src.candidates.png_candidate_extractor.detect_red_regions")
    def test_run_png_extraction_pipeline_no_regions(self, mock_detect):
        # Setup mock to return 0 red regions
        mock_detect.return_value = ([], Image.new("L", (100, 100), 0))
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a mock raw image
            mock_img_path = Path(tmp_dir) / "mock_plan.png"
            Image.new("RGB", (100, 100), "white").save(mock_img_path)
            
            # Use relative paths for inputs (which get resolved internally)
            relative_img_path = Path(tmp_dir) / "mock_plan.png"
            relative_out_dir = Path(tmp_dir) / "out"
            
            candidates = run_png_extraction_pipeline(
                image_path=relative_img_path,
                plan_id="mock_plan",
                output_root=relative_out_dir
            )
            
            self.assertEqual(candidates, [])
            
            # Check created empty files
            debug_mask_path = relative_out_dir / "debug" / "mock_plan_red_mask.png"
            crops_metadata_path = relative_out_dir / "debug" / "mock_plan_red_crops.json"
            ocr_results_path = relative_out_dir / "debug" / "mock_plan_ocr_results.json"
            candidates_path = relative_out_dir / "candidates" / "mock_plan_candidates.json"
            
            self.assertTrue(debug_mask_path.exists())
            self.assertTrue(crops_metadata_path.exists())
            self.assertTrue(ocr_results_path.exists())
            self.assertTrue(candidates_path.exists())
            
            # Read and verify empty candidates payload
            with open(candidates_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.assertEqual(payload["plan_id"], "mock_plan")
            self.assertEqual(payload["candidate_count"], 0)
            self.assertEqual(payload["candidates"], [])

    @patch("src.candidates.png_candidate_extractor.detect_red_regions")
    @patch("src.candidates.png_candidate_extractor.crop_red_regions")
    @patch("src.candidates.png_candidate_extractor.run_ocr_on_crops")
    def test_run_png_extraction_pipeline_happy_path(self, mock_ocr, mock_crop, mock_detect):
        # Setup mocks
        regions = [{"region_id": "RED-001", "bbox_image": [10, 10, 20, 20], "area_px": 400, "source": "red_annotation"}]
        mock_detect.return_value = (regions, Image.new("L", (100, 100), 0))
        
        crop_metadata = [{"region_id": "RED-001", "crop_path": "mock_crop.png", "bbox_image": [10, 10, 20, 20], "crop_bbox_image": [5, 5, 25, 25]}]
        mock_crop.return_value = crop_metadata
        
        # Simulate OCR unavailable/fallback
        mock_ocr.return_value = [{"region_id": "RED-001", "crop_path": "mock_crop.png", "ocr_text": "", "ocr_available": False, "requested_lang": "deu+eng", "used_lang": None, "warning": "missing"}]
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_img_path = Path(tmp_dir) / "mock_plan.png"
            Image.new("RGB", (100, 100), "white").save(mock_img_path)
            
            out_path = Path(tmp_dir) / "out"
            candidates = run_png_extraction_pipeline(
                image_path=mock_img_path,
                plan_id="mock_plan",
                output_root=out_path,
                clean_red=True
            )
            
            # Verify clean_red and output_root were passed to run_ocr_on_crops
            mock_ocr.assert_called_once_with(crop_metadata, psm=6, clean_red=True, output_root=out_path)
            
            self.assertEqual(len(candidates), 1)
            c = candidates[0]
            self.assertEqual(c["candidate_id"], "OP-001")
            self.assertEqual(c["source"], "png_red_annotation_region")
            self.assertEqual(c["confidence"], 0.20)

            # Check directories
            self.assertTrue((out_path / "crops").exists())
            self.assertTrue((out_path / "debug").exists())
            self.assertTrue((out_path / "candidates").exists())

            # Verify saved JSON has the server-compatible dict format
            candidates_path = out_path / "candidates" / "mock_plan_candidates.json"
            self.assertTrue(candidates_path.exists())
            with open(candidates_path, encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIsInstance(payload, dict)
            self.assertEqual(payload["plan_id"], "mock_plan")
            self.assertEqual(payload["candidate_count"], 1)
            self.assertIsInstance(payload["candidates"], list)


if __name__ == "__main__":
    unittest.main()
