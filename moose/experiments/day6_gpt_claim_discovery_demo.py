"""CLI demo for Moose Day 6 GPT-native workbook claim discovery.

This stops at code verification. It does not run investment reasoning.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moose.pipeline import run_financial_model_verification


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Moose Day 6 GPT-native claim discovery.")
    parser.add_argument("workbook_path", help="Path to a financial model workbook.")
    args = parser.parse_args()

    result = run_financial_model_verification(args.workbook_path)
    claim_result = result["claim_result"]
    verification = result["verification"]

    print("Extraction Mode")
    print(claim_result["extraction_mode"])
    print("\nGPT vs Fallback Comparison")
    print(json.dumps(claim_result.get("discovery_comparison", {}), indent=2))
    print("\nActive Grounded Claims")
    print(json.dumps(claim_result["claims"], indent=2))
    print("\nVerification Summary")
    print(json.dumps(verification["summary"], indent=2))
    print("\nVerified Facts")
    print(json.dumps(verification["verified_facts"], indent=2))
    print("\nDiagnostics")
    print(json.dumps(result.get("diagnostics", {}), indent=2))


if __name__ == "__main__":
    main()
