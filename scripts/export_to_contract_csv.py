#!/usr/bin/env python3
"""Convert candidate JSON files to the Riedel Bau contract CSV format."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.app.services.contract_export import generate_contract_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-json", required=True)
    parser.add_argument("--out-csv", required=True)
    args = parser.parse_args()

    json_path = Path(args.candidates_json).resolve()
    csv_path = Path(args.out_csv).resolve()

    if not json_path.exists():
        print(f"Error: {json_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    candidates = data if isinstance(data, list) else data.get("candidates", [])
    plan_id = json_path.stem.replace("_candidates", "")
    if isinstance(data, dict):
        plan_id = data.get("plan_id", plan_id)

    csv_bytes = generate_contract_csv(REPO_ROOT, plan_id, candidates)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_bytes(csv_bytes)
    print(f"Exported {plan_id} → {csv_path}")


if __name__ == "__main__":
    main()
