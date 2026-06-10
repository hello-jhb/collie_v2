"""
analyst_bundle.py — reviewable "analyst run package" assembled after ingestion.

This is a THIN audit/display layer, not a new extraction engine. It packages
what the SSOT already stores (bounded metrics, sheet inventory, raw insights,
catalog suggestions) into a single reviewable bundle that answers, at a glance:

  - Workbook Map      : did Collie look at the right tabs?
  - Verified Facts    : what does Collie believe (and from which cell)?
  - Issues / QC Flags : what did Collie refuse to trust, and why?
  - Status Summary    : quick QC health check
  - Business Plan Read: GPT interpretation, kept separate from facts
  - Catalog Suggestions: aliases to add to improve future extraction

It's the bridge between "engine output" and "human analyst trust" — and a fast
way to localize a remaining problem (classification vs section read vs units vs
validation vs memo).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import json
from pathlib import Path

import ssot

BUNDLE_VERSION = "2026-06-10.1"
BUNDLE_DIR = Path("assets/analyst_bundles")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric_row(name: str, rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric": name,
        "value": rec.get("display_value") or rec.get("normalized_value") or rec.get("raw_value"),
        "raw_value": rec.get("raw_value"),
        "normalized_value": rec.get("normalized_value"),
        "unit": rec.get("unit"),
        "scale": rec.get("scale"),
        "period": rec.get("period"),
        "status": rec.get("status"),
        "source_sheet": rec.get("source_sheet"),
        "source_cell": rec.get("source_cell"),
        "method": rec.get("extractor_confidence") or rec.get("method"),
        "notes": rec.get("validation_notes") or [],
        "candidate_count": len(rec.get("candidates") or []),
    }


# Statuses considered "trusted enough to display as a fact" vs "needs review".
_VERIFIED_STATUSES = {"verified", "derived", "inferred", "not_applicable"}
_ISSUE_STATUSES = {"missing", "suspicious", "conflict", "candidate_pool"}


def build_analyst_bundle(layer: str = "underwriting") -> dict[str, Any]:
    asset = ssot.load_ssot()
    layer_data = asset.get("layers", {}).get(layer)
    if not layer_data:
        return {
            "error": f"No SSOT layer found for {layer}",
            "bundle_version": BUNDLE_VERSION,
            "created_at": _now_iso(),
        }

    bounded_metrics = layer_data.get("bounded_metrics") or {}
    sheet_inventory = layer_data.get("sheet_inventory") or {}
    raw_insights = layer_data.get("raw_insights") or {}

    metric_rows = [
        _metric_row(name, rec)
        for name, rec in bounded_metrics.items()
        if isinstance(rec, dict)
    ]

    issues = [r for r in metric_rows if r.get("status") in _ISSUE_STATUSES]
    verified = [r for r in metric_rows if r.get("status") in _VERIFIED_STATUSES]

    # status summary — count each distinct status
    statuses = {r.get("status") for r in metric_rows}
    status_summary = {
        s: sum(1 for r in metric_rows if r.get("status") == s)
        for s in sorted(x for x in statuses if x)
    }

    return {
        "bundle_version": BUNDLE_VERSION,
        "created_at": _now_iso(),
        "asset_id": asset.get("asset_id"),
        "layer": layer,
        "source_file": layer_data.get("source_file"),
        "ingested_at": layer_data.get("ingested_at"),
        "workbook_map": {
            "all_sheets": sheet_inventory.get("all_sheets", []),
            "by_tier": sheet_inventory.get("by_tier", {}),
            "skipped_sheets": sheet_inventory.get("skipped_sheets", []),
            "low_priority_sheets": sheet_inventory.get("low_priority_sheets", []),
        },
        "verified_facts": verified,
        "issues": issues,
        "status_summary": status_summary,
        "business_plan_read": {
            "property_type": _safe_found(raw_insights, "property_type"),
            "deal_type": _safe_found(raw_insights, "deal_type"),
            "strategy": _safe_found(raw_insights, "strategy"),
            "key_risks": _safe_found(raw_insights, "key_risks"),
            "model_summary": raw_insights.get("model_summary") if isinstance(raw_insights, dict) else None,
        },
        "catalog_suggestions": layer_data.get("catalog_suggestions", []),
    }


def _safe_found(raw_insights: dict[str, Any], key: str) -> Any:
    found = raw_insights.get("found", {}) if isinstance(raw_insights, dict) else {}
    item = found.get(key)
    if isinstance(item, dict):
        return item.get("value")
    return item


def save_analyst_bundle(layer: str = "underwriting") -> dict[str, Any]:
    bundle = build_analyst_bundle(layer)
    if "error" in bundle:
        return bundle
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = bundle["created_at"].replace(":", "-").replace(".", "-")
    path = BUNDLE_DIR / f"{layer}_{stamp}.json"
    with open(path, "w") as f:
        json.dump(bundle, f, indent=2, default=str)
    bundle["bundle_path"] = str(path)
    return bundle
