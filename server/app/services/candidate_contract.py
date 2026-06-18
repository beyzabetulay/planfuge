from dataclasses import dataclass, field
from typing import Any


REQUIRED_CANDIDATE_FIELDS = ("candidate_id", "source", "bbox_image", "status")

OPTIONAL_CANDIDATE_FIELDS = (
    "label_type",
    "raw_text",
    "crop_path",
    "width_mm",
    "height_mm",
    "diameter_mm",
    "ra_value",
    "ok_value",
    "reference",
    "confidence",
    "review_comment",
)

ALLOWED_STATUS_VALUES = (
    "needs_review",
    "verified",
    "rejected",
    "duplicate_candidate",
)


@dataclass(frozen=True)
class CandidateValidationResult:
    plan_id: str | None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


def validate_candidate_payload(payload: dict[str, Any]) -> CandidateValidationResult:
    plan_id = payload.get("plan_id")
    raw_candidates = payload.get("candidates", [])

    warnings: list[str] = []
    errors: list[str] = []
    normalized_candidates: list[dict[str, Any]] = []

    if not isinstance(raw_candidates, list):
        return CandidateValidationResult(
            plan_id=plan_id,
            warnings=warnings,
            errors=["candidates must be a list"],
        )

    for index, raw_candidate in enumerate(raw_candidates):
        normalized_candidate = validate_candidate(raw_candidate, index, warnings, errors)
        if normalized_candidate is not None:
            normalized_candidates.append(normalized_candidate)

    return CandidateValidationResult(
        plan_id=plan_id,
        candidates=normalized_candidates,
        warnings=warnings,
        errors=errors,
    )


def validate_candidate(
    raw_candidate: Any,
    index: int,
    warnings: list[str],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(raw_candidate, dict):
        errors.append(f"candidate at index {index} must be an object")
        return None

    candidate_id = str(raw_candidate.get("candidate_id", f"index {index}"))
    missing_required_fields = [
        field_name for field_name in REQUIRED_CANDIDATE_FIELDS if field_name not in raw_candidate
    ]
    for field_name in missing_required_fields:
        errors.append(f"candidate {candidate_id} missing required field {field_name}")

    status = raw_candidate.get("status")
    has_invalid_status = "status" in raw_candidate and status not in ALLOWED_STATUS_VALUES
    if has_invalid_status:
        errors.append(f"candidate {candidate_id} has invalid status {status}")

    if missing_required_fields or has_invalid_status:
        return None

    normalized_candidate = dict(raw_candidate)
    for field_name in OPTIONAL_CANDIDATE_FIELDS:
        if field_name not in normalized_candidate:
            normalized_candidate[field_name] = None
            warnings.append(f"candidate {candidate_id} missing optional field {field_name}")

    return normalized_candidate
