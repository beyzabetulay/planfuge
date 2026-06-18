import json
import tempfile
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from server.app.api import app, calculate_opening, health, openings_csv
from server.app.schemas import CalculateOpeningRequest, CsvExportRequest


class ApiTests(unittest.TestCase):
    def test_health_endpoint(self) -> None:
        response = health()

        self.assertEqual(response["status"], "ok")

    def test_calculate_endpoint_returns_weight_and_csv_row(self) -> None:
        request = CalculateOpeningRequest.model_validate(
            {
                "geometry": "rectangular",
                "lengthCm": 20,
                "widthCm": 50,
                "heightCm": 25,
                "quantity": 2,
                "type": "Ceiling",
            }
        )

        response = calculate_opening(request)

        self.assertEqual(response["weightKg"], 22)
        self.assertEqual(response["reviewStatus"], "ready")
        self.assertEqual(response["csvRow"]["Type"], "Ceiling")

    def test_csv_endpoint_returns_csv(self) -> None:
        request = CsvExportRequest.model_validate(
            {
                "openings": [
                    {
                        "geometry": "round",
                        "lengthCm": 15,
                        "widthCm": 15,
                        "heightCm": 30,
                        "quantity": 3,
                    }
                ]
            }
        )

        response = openings_csv(request)
        body = response.body.decode("utf-8")

        self.assertIn("text/csv", response.media_type)
        self.assertTrue(body.startswith("Floor,Construction phase/Plan name"))
        self.assertIn("round", body)

    def test_candidates_endpoint_loads_valid_candidates(self) -> None:
        import asyncio

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

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/candidates/SP_U1_0003")
                    return response.json()

            data = asyncio.run(run_request())

        self.assertEqual(data["plan_id"], "SP_U1_0003")
        self.assertEqual(data["candidate_count"], 1)
        self.assertEqual(data["source"], "file")
        self.assertEqual(data["candidates"][0]["candidate_id"], "cand-001")

    def test_candidates_endpoint_missing_file_returns_warning(self) -> None:
        import asyncio

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/candidates/SP_U1_9999")
                    return response.json()

            data = asyncio.run(run_request())

        self.assertEqual(data["candidate_count"], 0)
        self.assertTrue(any("not found" in w for w in data["warnings"]))

    def test_sample_candidates_endpoint_returns_sample_data(self) -> None:
        import asyncio

        sample_payload = {
            "plan_id": "SAMPLE_DEMO",
            "candidates": [
                {
                    "candidate_id": "sample-wdb-001",
                    "source": "sample",
                    "label_type": "WDB",
                    "raw_text": "WDB 20/50 d=25",
                    "bbox_image": [1200, 3400, 180, 90],
                    "status": "needs_review",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            samples_dir = root / "data" / "samples"
            samples_dir.mkdir(parents=True)
            sample_file = samples_dir / "sample_candidates.json"
            sample_file.write_text(json.dumps(sample_payload))

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/candidates/sample")
                    return response.json()

            data = asyncio.run(run_request())

        self.assertEqual(data["source"], "sample")
        self.assertEqual(data["candidate_count"], 1)
        self.assertEqual(data["candidates"][0]["source"], "sample")

    def test_metadata_endpoint_loads_valid_metadata(self) -> None:
        import asyncio

        payload = {
            "plan_id": "SP_U1_0002",
            "image_width_px": 18896,
            "scale_text_visible": "M1:50",
            "source_type": "rendered_png",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metadata_dir = root / "data" / "metadata"
            metadata_dir.mkdir(parents=True)
            metadata_file = metadata_dir / "SP_U1_0002_metadata.json"
            metadata_file.write_text(json.dumps(payload))

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/metadata/SP_U1_0002")
                    return response.json()

            data = asyncio.run(run_request())

        self.assertEqual(data["plan_id"], "SP_U1_0002")
        self.assertTrue(data["exists"])
        self.assertEqual(data["metadata"]["image_width_px"], 18896)
        self.assertEqual(data["metadata"]["scale_text_visible"], "M1:50")

    def test_metadata_endpoint_missing_file_returns_warning(self) -> None:
        import asyncio

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/metadata/SP_U1_9999")
                    return response.json()

            data = asyncio.run(run_request())

        self.assertEqual(data["plan_id"], "SP_U1_9999")
        self.assertFalse(data["exists"])
        self.assertTrue(any("not found" in w for w in data["warnings"]))


if __name__ == "__main__":
    unittest.main()

