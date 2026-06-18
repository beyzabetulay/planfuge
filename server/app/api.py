from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
from server.app.services.json_export import export_verified_openings
from server.app.services.metadata_loader import load_metadata
from server.app.services.pandas_export import export_verified_openings_csv
from server.app.services.pipeline_status import check_pipeline_status
from server.app.services.plan_discovery import discover_plans
from server.app.services.review_saver import save_reviewed_candidates


app = FastAPI(title="Plan2Print API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/api/exports/json/{plan_id}")
def export_verified_json_endpoint(plan_id: str, candidates: list[dict[str, Any]]) -> Response:
    from fastapi.responses import FileResponse
    result = export_verified_openings(_get_project_root(), plan_id, candidates)
    return FileResponse(path=result["path"], filename=f"{plan_id}_verified_openings.json", media_type="application/json")


@app.post("/api/exports/csv/{plan_id}")
def export_verified_csv_endpoint(plan_id: str, candidates: list[dict[str, Any]]) -> Response:
    from fastapi.responses import FileResponse
    result = export_verified_openings_csv(_get_project_root(), plan_id, candidates)
    return FileResponse(path=result["path"], filename=f"{plan_id}_verified_openings.csv", media_type="text/csv")


@app.get("/api/status/{plan_id}")
def get_pipeline_status(plan_id: str) -> dict:
    return check_pipeline_status(_get_project_root(), plan_id)


@app.get("/api/plans")
def get_plans() -> dict:
    return {"plans": discover_plans(_get_project_root())}


@app.get("/api/images/pages/{plan_id}")
def get_plan_image(plan_id: str) -> Response:
    from fastapi import HTTPException
    
    image_path = _get_project_root() / "data" / "pages" / f"{plan_id}.png"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
        
    with open(image_path, "rb") as f:
        content = f.read()
    return Response(content=content, media_type="image/png")


@app.get("/api/images/crops/{filename}")
def get_crop_image(filename: str) -> Response:
    from fastapi import HTTPException
    
    image_path = _get_project_root() / "outputs" / "crops" / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Crop image not found")
        
    with open(image_path, "rb") as f:
        content = f.read()
    return Response(content=content, media_type="image/png")


@app.get("/api/images/overlays/{plan_id}")
def get_overlay_image(plan_id: str) -> Response:
    from fastapi import HTTPException
    
    image_path = _get_project_root() / "outputs" / "overlays" / f"{plan_id}_overlay.png"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Overlay image not found")
        
    with open(image_path, "rb") as f:
        content = f.read()
    return Response(content=content, media_type="image/png")

