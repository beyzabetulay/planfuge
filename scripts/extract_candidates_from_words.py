#!/usr/bin/env python3
"""Create candidate JSON from pre-extracted PDF words JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.candidates.pdf_words_candidate_extractor import extract_candidates_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--words",
        required=True,
        help="Path to data/words/<plan_id>_words.json",
    )
    parser.add_argument(
        "--out",
        default="outputs/candidates",
        help="Output directory for candidate JSON",
    )
    parser.add_argument(
        "--plan-id",
        help="Plan ID. Defaults to the words filename prefix.",
    )
    args = parser.parse_args()

    words_path = Path(args.words)
    plan_id = args.plan_id or _plan_id_from_words_path(words_path)
    output_path = Path(args.out) / f"{plan_id}_candidates.json"
    result = extract_candidates_json(words_path, output_path, plan_id=plan_id)

    print(f"Saved {result['candidate_count']} candidates to {output_path}")


def _plan_id_from_words_path(words_path: Path) -> str:
    stem = words_path.stem
    if stem.endswith("_words"):
        return stem[:-6]
    return stem


if __name__ == "__main__":
    main()
