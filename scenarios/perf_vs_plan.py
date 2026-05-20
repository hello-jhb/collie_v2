"""
Performance vs Plan scenario.

Input: at least one plan layer (underwriting or business_plan) AND at least
one actuals layer (actuals_2021/2022/2023/...) from SSOT.
Output: a chronological variance narrative — UW → actuals year by year,
folded in with the business plan if present.

Hard constraint: this scenario MUST NOT invent periods that aren't in SSOT.
If only actuals_2022 is present, the narrative discusses 2022. It does not
fabricate 2021 performance.
"""

from __future__ import annotations

import json
from typing import Any

import ssot
from scenarios._llm import complete, llm_available
from scenarios.profiles import filter_layer_metrics, _build_catalog_index


SYSTEM_PROMPT = """\
You are a real estate investment manager with institutional asset management
experience overseeing portfolios between approximately $150M and $1B in AUM.

You are doing a PERFORMANCE vs PLAN review. The user has provided:
- a plan layer (acquisition underwriting and/or business plan)
- one or more actuals layers (financial statements for specific years)

Your job: walk chronologically through what's present in SSOT and explain
how actuals compared to plan.

HARD RULES (violations are bugs):
- Discuss ONLY periods/layers that appear in the SSOT below.
  If actuals_2021 is missing, do NOT mention 2021 performance.
  If business_plan is missing, the comparison is actuals vs underwriting only.
- Never invent numbers or comparisons. Every cited number must be quoted from
  the SSOT, with file/sheet/cell.
- When a metric appears in both plan and actuals layers, compute the variance
  inline (% delta) and attribute the driver if it's evident from other metrics.
- Use clean markdown bullets. Bold key numbers. Be concise.
"""


USER_PROMPT_TEMPLATE = """\
Asset SSOT — relevant layers for performance review:

PLAN LAYERS PRESENT:
{plan_layers_json}

ACTUALS LAYERS PRESENT (chronological):
{actuals_layers_json}

Produce the narrative with this structure, SKIPPING any section whose source
layer is not in the SSOT above:

## Original Plan (Acquisition Underwriting)
  - Only if underwriting layer present.
  - Going-in basis, planned NOI, exit value, LTV, target IRR.

## Year-by-Year Actual vs Plan
  - One subsection per actuals layer in SSOT (e.g. ## 2021 Actual, ## 2022 Actual).
  - In each: actual NOI / revenue / expenses with variance vs UW (or BP if present).
  - Note variance drivers when evident (occupancy, expense overrun, lease-up timing).

## Revised Plan (Business Plan)
  - Only if business_plan layer present.
  - What changed vs UW: NOI assumption, exit, CapEx allocation, return target.

## Read
  - 2-3 bullets synthesizing performance trajectory and risk direction.
  - Distinguish going-in LTV (from UW) vs current LTV (if computable from
    actuals loan balance ÷ current value) — be explicit which is which.
"""


def _layers_subset(s: dict[str, Any], layer_names: list[str]) -> dict[str, Any]:
    """Return just the requested layers from the SSOT, as a dict."""
    return {name: s["layers"][name] for name in layer_names if name in s["layers"]}


def generate_perf_vs_plan() -> dict[str, Any]:
    """
    Read plan + actuals layers from SSOT and produce a chronological variance
    narrative. Returns {narrative, data_used} or {error}.
    """
    s = ssot.load_ssot()
    present = set(s["layers"].keys())

    plan_layers = [layer for layer in ("underwriting", "business_plan") if layer in present]
    actuals_layers = sorted(layer for layer in present if layer.startswith("actuals_"))

    if not plan_layers:
        return {
            "error": (
                "No plan layer in SSOT. Ingest an acquisition underwriting or "
                "business plan file first."
            )
        }
    if not actuals_layers:
        return {
            "error": (
                "No actuals layers in SSOT. Ingest at least one financial "
                "statement (e.g. 'Financial Statement 2022.xlsx')."
            )
        }

    if not llm_available():
        return {"error": "OPENAI_API_KEY is not set."}

    plan_data = _layers_subset(s, plan_layers)
    actuals_data = _layers_subset(s, actuals_layers)

    # Apply Performance vs Plan profile to every layer (build the catalog index
    # once and reuse it across all filter calls). Drops out going-in deal
    # structure and lease-specific metrics, keeping operating performance,
    # occupancy/income durability, and current debt health.
    catalog_index = _build_catalog_index()
    plan_filtered = {
        name: filter_layer_metrics(data, "perf_vs_plan", catalog_index)
        for name, data in plan_data.items()
    }
    actuals_filtered = {
        name: filter_layer_metrics(data, "perf_vs_plan", catalog_index)
        for name, data in actuals_data.items()
    }

    user_prompt = USER_PROMPT_TEMPLATE.format(
        plan_layers_json=json.dumps(plan_filtered, indent=2, default=str),
        actuals_layers_json=json.dumps(actuals_filtered, indent=2, default=str),
    )

    narrative = complete(SYSTEM_PROMPT, user_prompt, temperature=0.2)

    return {
        "scenario": "perf_vs_plan",
        "narrative": narrative,
        "data_used": {
            "plan_layers": plan_layers,
            "actuals_layers": actuals_layers,
            "source_files": sorted({
                layer_data["source_file"]
                for layer_data in {**plan_data, **actuals_data}.values()
            }),
            "metric_counts_after_profile": {
                **{f"plan/{k}": v["metric_count"] for k, v in plan_filtered.items()},
                **{f"actuals/{k}": v["metric_count"] for k, v in actuals_filtered.items()},
            },
        },
    }
