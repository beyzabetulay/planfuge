import unittest

from server.app.services.candidate_contract import (
    ALLOWED_STATUS_VALUES,
    OPTIONAL_CANDIDATE_FIELDS,
    REQUIRED_CANDIDATE_FIELDS,
    validate_candidate_payload,
)


class CandidateContractTests(unittest.TestCase):
    def test_loads_minimal_candidate_and_fills_optional_fields(self) -> None:
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

        result = validate_candidate_payload(payload)

        self.assertEqual(result.errors, [])
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.candidates[0]["candidate_id"], "cand-001")
        self.assertIsNone(result.candidates[0]["raw_text"])
        self.assertIn("candidate cand-001 missing optional field raw_text", result.warnings)

    def test_loads_richer_cv_candidate_without_dropping_extra_fields(self) -> None:
        payload = {
            "plan_id": "SP_U1_0003",
            "candidate_count": 1,
            "candidates": [
                {
                    "candidate_id": "cand-002",
                    "source": "cv",
                    "bbox_image": [100, 200, 50, 60],
                    "status": "verified",
                    "label_type": "WDB",
                    "raw_text": "WDB 20/50 d=25",
                    "width_mm": 200,
                    "height_mm": 500,
                    "confidence": 0.91,
                    "new_cv_field": "kept",
                }
            ],
        }

        result = validate_candidate_payload(payload)

        self.assertEqual(result.errors, [])
        self.assertEqual(result.candidates[0]["label_type"], "WDB")
        self.assertEqual(result.candidates[0]["new_cv_field"], "kept")
        self.assertEqual(result.candidate_count, 1)

    def test_reports_missing_required_fields_without_crashing(self) -> None:
        payload = {
            "plan_id": "SP_U1_0003",
            "candidates": [{"candidate_id": "cand-003", "status": "needs_review"}],
        }

        result = validate_candidate_payload(payload)

        self.assertEqual(result.candidates, [])
        self.assertIn("candidate cand-003 missing required field source", result.errors)
        self.assertIn("candidate cand-003 missing required field bbox_image", result.errors)

    def test_reports_invalid_status_values(self) -> None:
        payload = {
            "plan_id": "SP_U1_0003",
            "candidates": [
                {
                    "candidate_id": "cand-004",
                    "source": "cv",
                    "bbox_image": [10, 20, 30, 40],
                    "status": "done",
                }
            ],
        }

        result = validate_candidate_payload(payload)

        self.assertEqual(result.candidates, [])
        self.assertIn("candidate cand-004 has invalid status done", result.errors)

    def test_contract_lists_match_issue_requirements(self) -> None:
        self.assertEqual(REQUIRED_CANDIDATE_FIELDS, ("candidate_id", "source", "bbox_image", "status"))
        self.assertIn("raw_text", OPTIONAL_CANDIDATE_FIELDS)
        self.assertIn("verified", ALLOWED_STATUS_VALUES)


if __name__ == "__main__":
    unittest.main()
