"""
Deal Review scenario.

Input: only the underwriting layer of the SSOT.
Output: a tight executive summary of the deal thesis + a list of what's
missing to do deeper analysis.

Hard constraint: this scenario MUST NOT discuss actual performance, business
plans, or financial statements. If those topics come up, it's a prompt bug.
We enforce this structurally by only passing the underwriting layer to GPT.
"""

from __future__ import annotations

import json
from typing import Any

import ssot
from scenarios._llm import complete, llm_available
from scenarios.profiles import filter_layer_metrics


SYSTEM_PROMPT = """\
You are a real estate investment manager with institutional asset management
experience overseeing portfolios between approximately $150M and $1B in AUM.

You are doing a DEAL REVIEW. The user has provided ONLY the original
acquisition underwriting model for one asset. You have no other documents.

Your job:
1. Summarize the deal thesis from the underwriting evidence ONLY.
2. List what additional documents would unlock deeper analysis.

HARD RULES (violations are bugs):
- Use ONLY the metrics in the provided underwriting layer.
- Do NOT discuss actual performance, financial statements, business plans,
  rent rolls, or debt covenants. The user has not provided these.
- Do NOT invent numbers, periods, or comparisons.
- Reference each cited number with its sheet/cell (e.g. "$25.5M (Assumption!D9)").
- Use clean markdown bullets. Bold the numbers that matter. Be concise.
"""


USER_PROMPT_TEMPLATE = """\
Asset SSOT — underwriting layer only:

{underwriting_json}

Produce a Deal Review with this exact structure:

## Deal Thesis (from Acquisition Underwriting)
  - Going-in basis: purchase price + closing costs + initial CapEx (sum + show parts)
  - Going-in NOI and cap rate
  - Debt structure: LTV, loan amount, term, amortization
  - Exit assumption: exit value, take-out cap rate
  - Return targets: levered IRR, equity multiple (if available)

## Key Observations
  - 2-4 bullets on what stands out about the basis, leverage, or return profile.

## What's Missing to Go Deeper
  - 3-5 specific document requests, each tagged with what it would unlock:
    e.g. "Financial Statement 2022 → unlocks performance vs underwriting variance"
"""


def generate_deal_review() -> dict[str, Any]:
    """
    Read the underwriting layer from SSOT and produce a deal-review narrative.
    Returns {narrative, data_used} or {error} if preconditions aren't met.
    """
    s = ssot.load_ssot()
    underwriting = s["layers"].get("underwriting")

    if not underwriting:
        return {
            "error": (
                "No underwriting layer in SSOT. Ingest an acquisition "
                "underwriting file first (e.g. via ingest_to_ssot)."
            )
        }

    if not llm_available():
        return {"error": "OPENAI_API_KEY is not set."}

    # Apply the Deal Review profile — keep only Investment Basis, Valuation &
    # Returns, and the going-in subset of Debt & Leverage. Drops noise like
    # DSCR / Current LTV that belong to Performance vs Plan.
    underwriting_filtered = filter_layer_metrics(underwriting, "deal_review")

    user_prompt = USER_PROMPT_TEMPLATE.format(
        underwriting_json=json.dumps(underwriting_filtered, indent=2, default=str),
    )

    narrative = complete(SYSTEM_PROMPT, user_prompt, temperature=0.2)

    return {
        "scenario": "deal_review",
        "narrative": narrative,
        "data_used": {
            "layers": ["underwriting"],
            "source_files": [underwriting["source_file"]],
            "metric_count_unfiltered": underwriting["metric_count"],
            "metric_count_after_profile": underwriting_filtered["metric_count"],
        },
    }
