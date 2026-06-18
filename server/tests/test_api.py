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

    def test_save_reviews_endpoint_saves_payload(self) -> None:
        import asyncio

        payload = [
            {"candidate_id": "cand-001", "status": "verified"},
            {"candidate_id": "cand-002", "status": "rejected"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/api/reviews/SP_U1_0003", json=payload)
                    return response.json()

            data = asyncio.run(run_request())

            self.assertEqual(data["status"], "success")
            self.assertTrue("SP_U1_0003_reviewed_candidates.json" in data["path"])

            # Verify side effect
            saved_file = Path(data["path"])
            self.assertTrue(saved_file.exists())
            saved_data = json.loads(saved_file.read_text())
            self.assertEqual(saved_data["plan_id"], "SP_U1_0003")
            self.assertEqual(saved_data["candidate_count"], 2)

    def test_get_reviews_endpoint_loads_draft(self) -> None:
        import asyncio

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

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/reviews/SP_U1_0003")
                    return response.json()

            data = asyncio.run(run_request())

        self.assertEqual(data["plan_id"], "SP_U1_0003")
        self.assertEqual(data["candidate_count"], 1)
        self.assertEqual(data["source"], "review")
        self.assertEqual(data["candidates"][0]["status"], "verified")

    def test_json_export_endpoint_saves_and_filters_payload(self) -> None:
        import asyncio

        payload = [
            {"candidate_id": "cand-001", "status": "verified", "width_mm": 100},
            {"candidate_id": "cand-002", "status": "rejected", "width_mm": 200},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            async def run_requests() -> tuple[int, str]:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/api/exports/json/SP_U1_0001", json=payload)
                    return response.status_code, response.headers.get("content-type", "")

            status, content_type = asyncio.run(run_requests())

            self.assertEqual(status, 200)
            self.assertIn("application/json", content_type)

    def test_csv_export_endpoint_saves_and_filters_payload(self) -> None:
        import asyncio

        payload = [
            {"candidate_id": "cand-001", "status": "verified", "width_mm": 100},
            {"candidate_id": "cand-002", "status": "rejected", "width_mm": 200},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            async def run_requests() -> tuple[int, str]:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/api/exports/csv/SP_U1_0001", json=payload)
                    return response.status_code, response.headers.get("content-type", "")

            status, content_type = asyncio.run(run_requests())

            self.assertEqual(status, 200)
            self.assertIn("text/csv", content_type)

    def test_pipeline_status_endpoint_returns_flags(self) -> None:
        import asyncio

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            
            # Create one dummy file to test partial true state
            (root / "outputs" / "crops").mkdir(parents=True)

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/status/SP_U1_0009")
                    return response.json()

            data = asyncio.run(run_request())

            self.assertEqual(data["plan_id"], "SP_U1_0009")
            self.assertTrue(data["files"]["crops_dir"])
            self.assertFalse(data["files"]["export_csv"])

    def test_get_plans_endpoint_returns_discovered_plans(self) -> None:
        import asyncio

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pages_dir = root / "data" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "SP_U1_0001.png").touch()
            (pages_dir / "SP_U1_0002.png").touch()

            async def run_request() -> dict:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/api/plans")
                    return response.json()

            data = asyncio.run(run_request())

            self.assertIn("plans", data)
            self.assertEqual(len(data["plans"]), 2)
            self.assertEqual(data["plans"][0], "SP_U1_0001")

    def test_get_plan_image_returns_file_or_404(self) -> None:
        import asyncio

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pages_dir = root / "data" / "pages"
            pages_dir.mkdir(parents=True)
            
            # Create a dummy image
            dummy_image = pages_dir / "SP_U1_0001.png"
            dummy_image.write_bytes(b"dummy_png_bytes")

            async def run_requests() -> tuple[int, bytes, int]:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp_ok = await client.get("/api/images/pages/SP_U1_0001")
                    resp_missing = await client.get("/api/images/pages/MISSING")
                    return resp_ok.status_code, resp_ok.content, resp_missing.status_code

            status_ok, content, status_missing = asyncio.run(run_requests())

            self.assertEqual(status_ok, 200)
            self.assertEqual(content, b"dummy_png_bytes")
            self.assertEqual(status_missing, 404)

    def test_get_crop_image_returns_file_or_404(self) -> None:
        import asyncio

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            crops_dir = root / "outputs" / "crops"
            crops_dir.mkdir(parents=True)
            
            # Create a dummy crop image
            dummy_image = crops_dir / "SP_U1_0001_crop1.png"
            dummy_image.write_bytes(b"dummy_crop_bytes")

            async def run_requests() -> tuple[int, bytes, int]:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp_ok = await client.get("/api/images/crops/SP_U1_0001_crop1.png")
                    resp_missing = await client.get("/api/images/crops/missing_crop.png")
                    return resp_ok.status_code, resp_ok.content, resp_missing.status_code

            status_ok, content, status_missing = asyncio.run(run_requests())

            self.assertEqual(status_ok, 200)
            self.assertEqual(content, b"dummy_crop_bytes")
            self.assertEqual(status_missing, 404)

    def test_get_overlay_image_returns_file_or_404(self) -> None:
        import asyncio

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            overlays_dir = root / "outputs" / "overlays"
            overlays_dir.mkdir(parents=True)
            
            # Create a dummy overlay image
            dummy_image = overlays_dir / "SP_U1_0001_overlay.png"
            dummy_image.write_bytes(b"dummy_overlay_bytes")

            async def run_requests() -> tuple[int, bytes, int]:
                app.state.project_root = root
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp_ok = await client.get("/api/images/overlays/SP_U1_0001")
                    resp_missing = await client.get("/api/images/overlays/MISSING")
                    return resp_ok.status_code, resp_ok.content, resp_missing.status_code

            status_ok, content, status_missing = asyncio.run(run_requests())

            self.assertEqual(status_ok, 200)
            self.assertEqual(content, b"dummy_overlay_bytes")
            self.assertEqual(status_missing, 404)


if __name__ == "__main__":
    unittest.main()

