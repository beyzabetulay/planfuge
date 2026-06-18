from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import Response

from server.app.models import Opening, WeightConfig
from server.app.schemas import (
    CalculateOpeningRequest,
    CsvExportRequest,
    OpeningRequest,
    WeightConfigRequest,
)
from server.app.services.calculations import (
    calculate_volume_cm3,
    calculate_weight_kg,
    get_review_status,
)
from server.app.services.candidate_loader import (
    load_candidates,
    load_reviewed_candidates,
    load_sample_candidates,
)
from server.app.services.csv_export import CSV_COLUMNS, serialize_csv, to_csv_row
from server.app.services.metadata_loader import load_metadata
from server.app.services.review_saver import save_reviewed_candidates


app = FastAPI(title="Plan2Print API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "plan2print-api"}


@app.get("/api/export/contract")
def export_contract() -> dict[str, object]:
    config = WeightConfig()
    return {
        "columns": CSV_COLUMNS,
        "maxWeightKg": config.max_weight_kg,
        "densityKgPerM3": config.density_kg_per_m3,
    }


@app.post("/api/openings/calculate")
def calculate_opening(request: CalculateOpeningRequest) -> dict[str, object]:
    opening = opening_from_request(request)
    config = weight_config_from_request(request.config)

    return {
        "volumeCm3": round(calculate_volume_cm3(opening), 3),
        "weightKg": calculate_weight_kg(opening, config),
        "reviewStatus": get_review_status(opening, config),
        "csvRow": to_csv_row(opening, config),
    }


@app.post("/api/openings/csv")
def openings_csv(request: CsvExportRequest) -> Response:
    config = weight_config_from_request(request.config)
    openings = [opening_from_request(opening) for opening in request.openings]
    rows = [to_csv_row(opening, config) for opening in openings]
    return Response(content=serialize_csv(rows), media_type="text/csv")


def opening_from_request(request: OpeningRequest) -> Opening:
    return Opening(
        geometry=request.geometry,
        length_cm=request.length_cm,
        width_cm=request.width_cm,
        height_cm=request.height_cm,
        quantity=request.quantity,
        opening_type=request.opening_type,
        floor=request.floor,
        plan_name=request.plan_name,
        source_pdf=request.source_pdf,
        grid_coordinate=request.grid_coordinate,
        color_zone_id=request.color_zone_id,
        confidence=request.confidence,
        review_required=request.review_required,
    )


def weight_config_from_request(request: WeightConfigRequest) -> WeightConfig:
    return WeightConfig(
        density_kg_per_m3=request.density_kg_per_m3,
        max_weight_kg=request.max_weight_kg,
    )


def _get_project_root() -> Path:
    if hasattr(app.state, "project_root"):
        return app.state.project_root
    return Path.cwd()


@app.get("/api/candidates/sample")
def get_sample_candidates() -> dict:
    result = load_sample_candidates(_get_project_root())
    return asdict(result)


@app.get("/api/candidates/{plan_id}")
def get_candidates(plan_id: str) -> dict:
    result = load_candidates(_get_project_root(), plan_id)
    return asdict(result)


@app.get("/api/metadata/{plan_id}")
def get_metadata(plan_id: str) -> dict:
    result = load_metadata(_get_project_root(), plan_id)
    return asdict(result)


@app.get("/api/reviews/{plan_id}")
def get_reviews(plan_id: str) -> dict:
    result = load_reviewed_candidates(_get_project_root(), plan_id)
    return asdict(result)


@app.post("/api/reviews/{plan_id}")
def save_reviews(plan_id: str, candidates: list[dict[str, Any]]) -> dict:
    return save_reviewed_candidates(_get_project_root(), plan_id, candidates)

