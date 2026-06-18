import json
import tempfile
import unittest
from pathlib import Path

from src.candidates.pdf_words_candidate_extractor import (
    extract_candidates_from_words,
    extract_candidates_json,
)


class PdfWordsCandidateExtractorTest(unittest.TestCase):
    def test_extracts_candidate_from_nearby_words(self):
        words = [
            word("WDB", 10, 10, 35, 20),
            word("70/20", 40, 10, 75, 20),
            word("OK", 82, 10, 96, 20),
            word("-60", 100, 10, 125, 20),
            word("UKRD", 130, 10, 160, 20),
            word("Scale", 500, 10, 535, 20),
        ]

        candidates = extract_candidates_from_words(words)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0],
            {
                "candidate_id": "OP-001",
                "source": "pdf_words",
                "label_type": "WDB",
                "raw_text": "WDB 70/20 OK -60 UKRD",
                "bbox_pdf": [10.0, 10.0, 160.0, 20.0],
                "width_mm": 700,
                "height_mm": 200,
                "diameter_mm": None,
                "ra_value": None,
                "ok_value": -60,
                "reference": "UKRD",
                "confidence": 0.85,
                "status": "needs_review",
            },
        )

    def test_extracts_ddp_hsi_without_duplicate_hsi_candidate(self):
        words = [
            word("DDP", 10, 10, 30, 20),
            word("HSI150", 36, 10, 82, 20),
            word("RA", 90, 10, 106, 20),
            word("-50", 112, 10, 138, 20),
            word("UKRD", 144, 10, 175, 20),
        ]

        candidates = extract_candidates_from_words(words)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["label_type"], "DDP")
        self.assertEqual(candidates[0]["diameter_mm"], 150)
        self.assertEqual(candidates[0]["ra_value"], -50)
        self.assertEqual(candidates[0]["reference"], "UKRD")

    def test_returns_empty_candidates_for_no_anchors(self):
        self.assertEqual(
            extract_candidates_from_words([word("M", 1, 1, 2, 2)]),
            [],
        )

    def test_loads_words_and_saves_candidates_json(self):
        words = [word("DDB130/140", 5, 7, 80, 20)]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            words_path = tmp_path / "SP_U1_0003_words.json"
            output_path = tmp_path / "SP_U1_0003_candidates.json"
            words_path.write_text(json.dumps(words), encoding="utf-8")

            result = extract_candidates_json(
                words_path,
                output_path,
                plan_id="SP_U1_0003",
            )

            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(saved, result)
            self.assertEqual(saved["plan_id"], "SP_U1_0003")
            self.assertEqual(saved["candidate_count"], 1)
            self.assertEqual(saved["candidates"][0]["label_type"], "DDB")
            self.assertEqual(saved["candidates"][0]["width_mm"], 1300)
            self.assertEqual(saved["candidates"][0]["height_mm"], 1400)


def word(text, x0, y0, x1, y1, page=1):
    return {
        "text": text,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        "page": page,
    }


if __name__ == "__main__":
    unittest.main()
