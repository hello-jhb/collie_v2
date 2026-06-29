"""Lightweight CLI demo for Moose Day 4 claim extraction prep."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moose.pipeline import run_financial_model_claim_extraction, run_intake


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Moose Day 4 financial model claim extraction.")
    parser.add_argument("workbook_path", help="Path to a financial model workbook.")
    args = parser.parse_args()

    intake = run_intake(args.workbook_path)
    print("Intake Summary")
    print(json.dumps({
        "document_identity": intake.document_identity,
        "route": intake.route,
    }, indent=2))

    if intake.route.get("pipeline_name") != "financial_model_pipeline":
        print("\nClaim extraction skipped")
        print(f"Expected financial_model_pipeline, got {intake.route.get('pipeline_name')}.")
        return

    result = run_financial_model_claim_extraction(args.workbook_path)
    print("\nWorkbook Understanding")
    print(json.dumps({
        "orientation": result.workbook_orientation,
        "model_brief": result.model_brief,
    }, indent=2))
    print("\nMental Model")
    print(json.dumps(result.mental_model, indent=2))
    print("\nEvidence Pack")
    print(json.dumps({
        "important_sheet_names": result.evidence_pack.get("important_sheet_names"),
        "candidate_neighborhood_count": len(result.evidence_pack.get("candidate_neighborhoods", [])),
        "caveats": result.evidence_pack.get("caveats"),
    }, indent=2))
    print("\nExtraction Mode")
    print(result.extraction_mode)
    print("\nExtracted Claims")
    print(json.dumps(result.claims, indent=2))
    if result.rejected_claims:
        print("\nRejected Claims")
        print(json.dumps(result.rejected_claims, indent=2))


if __name__ == "__main__":
    main()
