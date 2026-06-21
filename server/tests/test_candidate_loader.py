import tempfile
import json
import unittest
from pathlib import Path

from PIL import Image

from server.app.services.candidate_loader import load_candidates


class CandidateLoaderTests(unittest.TestCase):
    def test_loads_valid_candidate_json_and_returns_validated_result(self) -> None:
        payload = {
            "plan_id": "SP_U1_0003",
            "candidates": [
                {
                    "candidate_id": "cand-001",
                    "source": "cv",
                    "bbox_image": [10, 20, 30, 40],
                    "status": "needs_review",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "outputs" / "candidates"
            candidates_dir.mkdir(parents=True)
            candidate_file = candidates_dir / "SP_U1_0003_candidates.json"
            candidate_file.write_text(json.dumps(payload))

            result = load_candidates(root, "SP_U1_0003")

        self.assertEqual(result.plan_id, "SP_U1_0003")
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.candidates[0]["candidate_id"], "cand-001")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.source, "file")


    def test_missing_file_returns_warning_and_empty_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = load_candidates(root, "SP_U1_9999")

        self.assertEqual(result.plan_id, "SP_U1_9999")
        self.assertEqual(result.candidate_count, 0)
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.source, "empty")
        self.assertTrue(any("not found" in w for w in result.warnings))
        self.assertEqual(result.errors, [])


    def test_malformed_json_returns_error_and_empty_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "outputs" / "candidates"
            candidates_dir.mkdir(parents=True)
            candidate_file = candidates_dir / "SP_U1_0003_candidates.json"
            candidate_file.write_text("{broken json!!!")

            result = load_candidates(root, "SP_U1_0003")

        self.assertEqual(result.plan_id, "SP_U1_0003")
        self.assertEqual(result.candidate_count, 0)
        self.assertEqual(result.candidates, [])
        self.assertTrue(any("failed to read" in e for e in result.errors))


    def test_invalid_candidates_propagate_validation_errors(self) -> None:
        payload = {
            "plan_id": "SP_U1_0003",
            "candidates": [{"candidate_id": "bad-001", "status": "needs_review"}],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "outputs" / "candidates"
            candidates_dir.mkdir(parents=True)
            candidate_file = candidates_dir / "SP_U1_0003_candidates.json"
            candidate_file.write_text(json.dumps(payload))

            result = load_candidates(root, "SP_U1_0003")

        self.assertEqual(result.candidates, [])
        self.assertTrue(any("missing required field source" in e for e in result.errors))
        self.assertEqual(result.source, "file")

    def test_optional_fields_are_filled_with_null(self) -> None:
        payload = {
            "plan_id": "SP_U1_0003",
            "candidates": [
                {
                    "candidate_id": "cand-005",
                    "source": "cv",
                    "bbox_image": [10, 20, 30, 40],
                    "status": "needs_review",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "outputs" / "candidates"
            candidates_dir.mkdir(parents=True)
            candidate_file = candidates_dir / "SP_U1_0003_candidates.json"
            candidate_file.write_text(json.dumps(payload))

            result = load_candidates(root, "SP_U1_0003")

        self.assertIsNone(result.candidates[0]["raw_text"])
        self.assertIsNone(result.candidates[0]["label_type"])
        self.assertTrue(any("missing optional field" in w for w in result.warnings))

    def test_load_candidates_creates_boxed_crop_preview_for_existing_payload(self) -> None:
        payload = {
            "plan_id": "SP_U1_0003",
            "candidates": [
                {
                    "candidate_id": "OP-064",
                    "source": "pdf_words",
                    "bbox_image": [20, 30, 40, 20],
                    "status": "needs_review",
                    "crop_path": None,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_dir = root / "outputs" / "candidates"
            pages_dir = root / "data" / "pages"
            candidates_dir.mkdir(parents=True)
            pages_dir.mkdir(parents=True)
            candidate_file = candidates_dir / "SP_U1_0003_candidates.json"
            candidate_file.write_text(json.dumps(payload))
            page = Image.new("RGB", (120, 100), "white")
            for x in range(20, 60):
                page.putpixel((x, 30), (0, 0, 0))
            page.save(pages_dir / "SP_U1_0003.png")

            result = load_candidates(root, "SP_U1_0003")

            crop_path = Path(result.candidates[0]["crop_path"])
            self.assertTrue(crop_path.exists())
            with Image.open(crop_path) as crop:
                red_pixels = [
                    pixel
                    for pixel in crop.convert("RGB").getdata()
                    if pixel[0] > 200 and pixel[1] < 80 and pixel[2] < 80
                ]
            self.assertGreater(len(red_pixels), 0)

            saved = json.loads(candidate_file.read_text())
            self.assertEqual(saved["candidates"][0]["crop_path"], str(crop_path))


if __name__ == "__main__":
    unittest.main()
