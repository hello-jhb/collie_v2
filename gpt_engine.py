import os

import json

import streamlit as st

from openai import OpenAI

api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)


SYSTEM_PROMPT = """
You are a senior institutional real estate asset management professional.

You are reviewing a property using structured extracted data from:
- acquisition underwriting
- business plan
- actual financial statements
- metric catalog scan
- missing metric report
- core question framework

Your job is to generate decision-oriented asset management analysis.

Rules:
1. Do not invent numbers.
2. Use only the provided structured data.
3. Python has already calculated the metrics. Do not recalculate unless asked.
4. Distinguish clearly between:
   - acquisition underwriting = original baseline
   - business plan = updated expectation
   - actuals = operating reality
5. Do not just say “high confidence” or “partial confidence.”
   Convert coverage into narrative judgment.
6. If data is missing, explain what conclusion is limited and why it matters.
7. Keep the writing concise and executive-level.
8. Focus on:
   - performance vs plan
   - income durability
   - leverage health
   - capital justification
   - basis / value support
   - risk trend
9. When discussing IRR or acceptable returns, state that the system needs the investor’s required return threshold.
10. Prefer synthesis over long lists.
"""


def generate_asset_management_narrative(analysis_context):
    prompt = {
        "task": "Generate the main asset management performance narrative from the structured evidence.",
        "desired_structure": [
            "One-line diagnosis",
            "Critical metric summary",
            "Core question assessment",
            "Key risks",
            "2023 planning implications",
            "Missing data / limitations"
        ],
        "analysis_context": analysis_context,
    }

    response = client.responses.create(
        model="gpt-5.5",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt, default=str)}
        ],
    )

    return response.output_text


def ask_gpt(question, known_result, flexible_result, analysis_context):
    prompt = {
        "task": "Answer the user's follow-up question using the structured property analysis context.",
        "user_question": question,
        "known_precise_extraction": known_result,
        "flexible_metric_scan_summary": {
            "total_metrics": flexible_result.get("total_metrics"),
            "extracted_count": flexible_result.get("extracted_count"),
            "missing_count": flexible_result.get("missing_count"),
            "sample_extracted_metrics": flexible_result.get("extracted_metrics", [])[:50],
            "sample_missing_metrics": flexible_result.get("missing_metrics", [])[:50],
        },
        "analysis_context": analysis_context,
    }

    response = client.responses.create(
        model="gpt-5.5",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt, default=str)}
        ],
    )

    return response.output_text
