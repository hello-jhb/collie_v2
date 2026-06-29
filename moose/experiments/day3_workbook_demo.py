"""Lightweight CLI demo for Moose Day 3 workbook comprehension."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moose.pipeline import run_financial_model_comprehension, run_intake


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Moose Day 3 workbook comprehension.")
    parser.add_argument("workbook_path", help="Path to a financial model workbook.")
    args = parser.parse_args()

    intake = run_intake(args.workbook_path)
    print("Intake Result")
    print(json.dumps(intake.as_dict(), indent=2))

    if intake.route.get("pipeline_name") != "financial_model_pipeline":
        print("\nWorkbook comprehension skipped")
        print(f"Expected financial_model_pipeline, got {intake.route.get('pipeline_name')}.")
        return

    result = run_financial_model_comprehension(args.workbook_path)
    print("\nWorkbook Orientation")
    print(json.dumps(result.workbook_orientation, indent=2))
    print("\nModel Brief")
    print(json.dumps(result.model_brief, indent=2))


if __name__ == "__main__":
    main()
