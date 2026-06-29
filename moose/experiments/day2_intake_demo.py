"""Lightweight CLI demo for Moose Day 2 intake."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from moose.pipeline import run_intake


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Moose Day 2 intake on a file.")
    parser.add_argument("file_path", help="Path to the file to identify and route.")
    args = parser.parse_args()

    result = run_intake(args.file_path)
    identity = result.document_identity
    context = result.resolved_context
    route = result.route

    print(f"Document Type: {identity.get('document_type')}")
    print(f"Confidence: {identity.get('confidence')}")
    print(f"Lifecycle Stage: {context.get('lifecycle_stage')}")
    print(f"Decision Layer: {context.get('decision_layer')}")
    print(f"Functional Work: {context.get('functional_work')}")
    print(f"Related Initiatives: {context.get('related_initiatives')}")
    print(f"Recommended Pipeline: {context.get('recommended_pipeline')}")
    print(f"Next Agent: {route.get('next_agent')}")
    print(f"Human Review Required: {route.get('human_review_required')}")


if __name__ == "__main__":
    main()
