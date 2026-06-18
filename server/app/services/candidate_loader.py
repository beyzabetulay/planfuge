import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from server.app.services.candidate_contract import validate_candidate_payload


@dataclass(frozen=True)
class CandidateLoadResult:
    plan_id: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    candidate_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source: str = "empty"


SAMPLE_CANDIDATES_PATH = Path("data") / "samples" / "sample_candidates.json"


def load_candidates(project_root: Path, plan_id: str) -> CandidateLoadResult:
    candidate_path = project_root / "outputs" / "candidates" / f"{plan_id}_candidates.json"
    return _load_and_validate(candidate_path, plan_id, source="file")


def load_sample_candidates(project_root: Path) -> CandidateLoadResult:
    sample_path = project_root / SAMPLE_CANDIDATES_PATH
    return _load_and_validate(sample_path, fallback_plan_id="SAMPLE_DEMO", source="sample")


def load_reviewed_candidates(project_root: Path, plan_id: str) -> CandidateLoadResult:
    review_path = project_root / "outputs" / "reviews" / f"{plan_id}_reviewed_candidates.json"
    return _load_and_validate(review_path, fallback_plan_id=plan_id, source="review")


def _load_and_validate(
    path: Path,
    fallback_plan_id: str,
    source: str,
) -> CandidateLoadResult:
    if not path.is_file():
        level = "warnings" if source in ("file", "review") else "errors"
        message = f"candidate file not found: {path}"
        if source == "sample":
            message = f"sample {message}"
        kwargs = {level: [message]}
        return CandidateLoadResult(plan_id=fallback_plan_id, **kwargs)

    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except (json.JSONDecodeError, OSError) as exc:
        return CandidateLoadResult(
            plan_id=fallback_plan_id,
            errors=[f"failed to read candidate file: {exc}"],
        )

    if not isinstance(payload, dict):
        return CandidateLoadResult(
            plan_id=fallback_plan_id,
            errors=["candidate file must contain a JSON object"],
        )

    plan_id = payload.get("plan_id", fallback_plan_id)
    validation = validate_candidate_payload(payload)

    return CandidateLoadResult(
        plan_id=plan_id,
        candidates=validation.candidates,
        candidate_count=validation.candidate_count,
        warnings=validation.warnings,
        errors=validation.errors,
        source=source,
    )
