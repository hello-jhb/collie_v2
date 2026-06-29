"""Lightweight CLI demo for Moose Day 6 reasoning from verified facts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moose.pipeline import run_financial_model_reasoning


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Moose Day 6 verified-facts reasoning.")
    parser.add_argument("workbook_path", help="Path to a financial model workbook.")
    parser.add_argument(
        "--question",
        default="What does the verified financial model evidence show?",
        help="Question to answer from verified facts only.",
    )
    args = parser.parse_args()

    result = run_financial_model_reasoning(args.workbook_path, question=args.question)
    reasoning = result["reasoning"]

    print("Verification Summary")
    print(json.dumps(result["verification_run"]["verification"]["summary"], indent=2))
    print("\nReasoning Readout")
    print(json.dumps(reasoning, indent=2))


if __name__ == "__main__":
    main()
