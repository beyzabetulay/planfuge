import json
import tempfile
import unittest
from pathlib import Path

from server.app.services.candidate_loader import load_reviewed_candidates


class ReviewLoaderTests(unittest.TestCase):
    def test_loads_reviewed_candidates_from_file(self) -> None:
        payload = {
            "plan_id": "SP_U1_0003",
            "saved_at": "2023-10-01T12:00:00Z",
            "candidate_count": 1,
            "candidates": [
                {
                    "candidate_id": "cand-001",
                    "source": "cv",
                    "bbox_image": [10, 20, 30, 40],
                    "status": "verified",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reviews_dir = root / "outputs" / "reviews"
            reviews_dir.mkdir(parents=True)
            review_file = reviews_dir / "SP_U1_0003_reviewed_candidates.json"
            review_file.write_text(json.dumps(payload))

            result = load_reviewed_candidates(root, "SP_U1_0003")

        self.assertEqual(result.plan_id, "SP_U1_0003")
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.source, "review")
        self.assertEqual(result.candidates[0]["status"], "verified")
        self.assertEqual(result.errors, [])

    def test_missing_review_file_returns_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = load_reviewed_candidates(root, "SP_U1_9999")

        self.assertEqual(result.plan_id, "SP_U1_9999")
        self.assertEqual(result.candidate_count, 0)
        self.assertTrue(any("not found" in w for w in result.warnings))


if __name__ == "__main__":
    unittest.main()
