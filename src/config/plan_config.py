"""Plan configuration model and loader."""

import json
from pathlib import Path
from typing import Any


class PlanConfig:
    def __init__(self, plan_id: str, data: dict[str, Any] | None = None) -> None:
        self.plan_id = plan_id
        if data is None:
            data = {}

        self.scale: int = int(data.get("scale", 50))
        self.default_height_cm: float = float(data.get("default_height_cm", 30.0))
        
        # Grid layout configuration
        grid_data = data.get("grid", {})
        self.grid_anchors = grid_data.get("anchors")
        
        # Color zones configuration
        self.color_zones: list[dict[str, Any]] = data.get("color_zones", [])

    @classmethod
    def load_for_plan(cls, project_root: Path, plan_id: str) -> PlanConfig:
        config_path = project_root / "data" / "config" / f"{plan_id}_config.json"
        if not config_path.is_file():
            return cls(plan_id)

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(plan_id, data)
        except Exception as e:
            # Fall back to defaults on error
            print(f"Warning: Failed to load config for plan {plan_id}: {e}")
            return cls(plan_id)
