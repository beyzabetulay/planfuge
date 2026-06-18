import math

from server.app.models import (
    GEOMETRY_RECTANGULAR,
    GEOMETRY_ROUND,
    STATUS_READY,
    STATUS_REVIEW_REQUIRED,
    STATUS_SPLIT_RECOMMENDED,
    Opening,
    WeightConfig,
)

CM3_PER_M3 = 1_000_000


def calculate_volume_cm3(opening: Opening) -> float:
    if opening.geometry == GEOMETRY_ROUND:
        radius_cm = opening.length_cm / 2
        return math.pi * radius_cm * radius_cm * opening.height_cm

    if opening.geometry == GEOMETRY_RECTANGULAR:
        return opening.length_cm * opening.width_cm * opening.height_cm

    raise ValueError(f"Unsupported geometry: {opening.geometry}")


def calculate_weight_kg(opening: Opening, config: WeightConfig = WeightConfig()) -> float:
    volume_m3 = calculate_volume_cm3(opening) / CM3_PER_M3
    weight_kg = volume_m3 * config.density_kg_per_m3 * opening.quantity
    return round(weight_kg, 1)


def get_review_status(opening: Opening, config: WeightConfig = WeightConfig()) -> str:
    if calculate_weight_kg(opening, config) > config.max_weight_kg:
        return STATUS_SPLIT_RECOMMENDED

    if opening.review_required:
        return STATUS_REVIEW_REQUIRED

    return STATUS_READY

