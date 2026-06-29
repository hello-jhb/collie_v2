"""Moose Streamlit prototype.

Run with:
    streamlit run moose_app.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from moose.pipeline import run_financial_model_reasoning


REPO_ROOT = Path(__file__).resolve().parent
SAMPLE_WORKBOOK = REPO_ROOT / "sample" / "BAC_vClosing.xlsx"
BASELINE_FACTS = [
    "purchase_price",
    "total_project_cost",
    "debt_amount",
    "equity_required",
    "loan_to_value",
    "interest_rate",
    "stabilized_noi",
    "levered_irr",
    "unlevered_irr",
    "equity_multiple",
    "unlevered_equity_multiple",
    "exit_cap_rate",
    "sale_value",
]


def main() -> None:
    st.set_page_config(page_title="Moose", page_icon="M", layout="wide")
    _style()

    st.title("Moose")
    st.caption("Agent-centric workbook understanding, code-grounded verification, and transparent investment readouts.")

    with st.sidebar:
        st.header("Upload")
        uploaded = st.file_uploader("Excel workbook", type=["xlsx", "xlsm", "xltx", "xltm"])
        use_sample = st.checkbox("Use sample/BAC_vClosing.xlsx", value=uploaded is None)
        run_clicked = st.button("Run Moose", type="primary", use_container_width=True)
        st.divider()
        st.caption("LLM calls use OPENAI_API_KEY or Streamlit secrets. Without a key, Moose uses the Collie v2 fallback bridge and reports that clearly.")

    if not run_clicked:
        _empty_state()
        return

    try:
        workbook_path, display_name = _resolve_workbook(uploaded, use_sample)
    except ValueError as exc:
        st.error(str(exc))
        return

    with st.status("Running Moose pipeline...", expanded=True) as status:
        st.write("Identifying file and understanding workbook.")
        try:
            result = run_financial_model_reasoning(workbook_path)
        except Exception as exc:
            status.update(label="Moose run failed", state="error")
            st.error(f"Moose could not process this workbook: {type(exc).__name__}: {exc}")
            return
        status.update(label="Moose pipeline complete", state="complete")

    _render_results(display_name, result)


def _resolve_workbook(uploaded: Any, use_sample: bool) -> tuple[Path, str]:
    if uploaded is not None:
        suffix = Path(uploaded.name).suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(uploaded.getbuffer())
            return Path(handle.name), uploaded.name
    if use_sample and SAMPLE_WORKBOOK.exists():
        return SAMPLE_WORKBOOK, "sample/BAC_vClosing.xlsx"
    raise ValueError("Upload a workbook or enable the sample workbook.")


def _render_results(display_name: str, result: dict[str, Any]) -> None:
    verification_run = result["verification_run"]
    claim_result = verification_run["claim_result"]
    verification = verification_run["verification"]
    reasoning = result["reasoning"]
    diagnostics = verification_run.get("diagnostics", {})

    intake = claim_result.get("intake_result", {})
    document_identity = intake.get("document_identity", {})
    route = intake.get("route", {})
    orientation = claim_result.get("workbook_orientation", {})

    st.subheader("File Understanding")
    col1, col2, col3, col4 = st.columns(4)
    _metric_card(col1, "File", display_name)
    _metric_card(col2, "Detected Type", document_identity.get("document_type", "unknown"))
    _metric_card(col3, "Confidence", _pct(document_identity.get("confidence")))
    _metric_card(col4, "Pipeline", route.get("pipeline_name", "human_review"))

    st.markdown(
        f"""
        <div class="moose-card">
          <strong>This appears to be an acquisition underwriting model.</strong><br>
          <span>{orientation.get("reasoning", "Moose generated no orientation reasoning.")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_timeline(diagnostics)
    _render_reasoning(reasoning)
    _render_facts(verification.get("verified_facts", []), claim_result)
    _render_caveats(verification)
    _render_evidence(verification.get("verified_facts", []))
    _render_trace(claim_result, verification_run, reasoning)


def _render_timeline(diagnostics: dict[str, Any]) -> None:
    st.subheader("Processing Timeline")
    stages = [
        ("File identified", diagnostics.get("intake", {})),
        ("Workbook understood", diagnostics.get("mental_model", {})),
        ("Mental model created", diagnostics.get("mental_model", {})),
        ("Claims discovered", diagnostics.get("claim_discovery", {})),
        ("Claims verified", diagnostics.get("verification", {})),
        ("Investment read generated", {"status": "passed"}),
    ]
    cols = st.columns(3)
    for idx, (label, payload) in enumerate(stages):
        with cols[idx % 3]:
            status = payload.get("status", "not_run")
            st.markdown(
                f"<div class='moose-card'><strong>{_status_badge(status)} {label}</strong><br>{_stage_summary(payload)}</div>",
                unsafe_allow_html=True,
            )
            with st.expander(f"Debug: {label}"):
                st.json(payload)


def _render_reasoning(reasoning: dict[str, Any]) -> None:
    st.subheader("Agent Reasoning")
    st.markdown(
        f"<div class='moose-card'><strong>Executive Read</strong><br>{reasoning.get('answer_summary', '')}</div>",
        unsafe_allow_html=True,
    )
    sections = reasoning.get("sections") or {}
    if sections:
        cols = st.columns(2)
        for idx, (title, body) in enumerate(sections.items()):
            with cols[idx % 2]:
                st.markdown(f"<div class='moose-card'><strong>{title}</strong><br>{body}</div>", unsafe_allow_html=True)


def _render_facts(facts: list[dict[str, Any]], claim_result: dict[str, Any]) -> None:
    st.subheader("Verified Facts")
    baseline = {fact.get("metric_or_subject") for fact in facts if fact.get("metric_or_subject") in BASELINE_FACTS}
    gpt = [fact for fact in facts if fact.get("fact_origin") == "gpt_native"]
    fallback = [fact for fact in facts if fact.get("fact_origin") == "fallback"]
    st.caption(
        f"{len(baseline)} of 13 baseline facts recovered. "
        f"GPT-native facts: {len(gpt)}. Fallback-derived facts: {len(fallback)}. "
        f"Mode: {claim_result.get('extraction_mode')}."
    )
    rows = [
        {
            "metric": fact.get("metric_or_subject"),
            "value": fact.get("verified_value"),
            "unit": fact.get("unit"),
            "status": fact.get("verification_status"),
            "origin": fact.get("fact_origin"),
            "source": fact.get("source"),
            "caveat": "; ".join(fact.get("caveats", [])[:2]),
        }
        for fact in facts
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_caveats(verification: dict[str, Any]) -> None:
    st.subheader("Issues / Caveats")
    summary = verification.get("summary", {})
    st.markdown(
        f"""
        <div class="moose-card">
          <strong>{summary.get("claims_total", 0)} claims checked</strong><br>
          {summary.get("verified", 0)} verified, {summary.get("verified_with_caveat", 0)} verified with caveat,
          {summary.get("needs_review", 0)} need review, {summary.get("contradicted", 0)} contradicted,
          {summary.get("rejected", 0)} rejected.
        </div>
        """,
        unsafe_allow_html=True,
    )
    caveats = verification.get("caveats", [])
    if caveats:
        for caveat in caveats[:20]:
            st.warning(caveat)
    else:
        st.success("No verification caveats reported.")


def _render_evidence(facts: list[dict[str, Any]]) -> None:
    st.subheader("Evidence Drawer")
    for fact in facts:
        with st.expander(f"{fact.get('metric_or_subject')} | {fact.get('source')} | {fact.get('verification_status')}"):
            st.write("Checks")
            st.dataframe(pd.DataFrame(fact.get("checks", [])), use_container_width=True, hide_index=True)
            st.write("Caveats")
            st.json(fact.get("caveats", []))


def _render_trace(claim_result: dict[str, Any], verification_run: dict[str, Any], reasoning: dict[str, Any]) -> None:
    st.subheader("Agent Trace")
    with st.expander("Intake output"):
        st.json(claim_result.get("intake_result", {}))
    with st.expander("Mental model"):
        st.json(claim_result.get("mental_model", {}))
    with st.expander("Claim discovery and fallback"):
        st.json({
            "mode": claim_result.get("extraction_mode"),
            "comparison": claim_result.get("discovery_comparison", {}),
            "diagnostics": claim_result.get("diagnostics", {}),
        })
    with st.expander("Grounding and verification stats"):
        st.json(verification_run.get("diagnostics", {}))
    with st.expander("Reasoning raw output"):
        st.json(reasoning)


def _empty_state() -> None:
    st.info("Upload an Excel workbook or use the included BAC sample, then run Moose.")
    st.markdown(
        """
        Moose flow: upload workbook -> identify file -> understand workbook -> discover claims with agents
        -> verify facts with code -> explain the investment situation.
        """
    )


def _metric_card(column: Any, label: str, value: Any) -> None:
    with column:
        st.markdown(f"<div class='moose-card'><span>{label}</span><br><strong>{value}</strong></div>", unsafe_allow_html=True)


def _stage_summary(payload: dict[str, Any]) -> str:
    if "summary" in payload:
        return json.dumps(payload["summary"])
    if "mode" in payload:
        return str(payload["mode"])
    if "document_type" in payload:
        return f"{payload.get('document_type')} via {payload.get('route')}"
    if "important_sheets" in payload:
        return ", ".join(payload.get("important_sheets", [])[:3])
    return str(payload.get("status", "not run"))


def _status_badge(status: str) -> str:
    if status in {"passed", "complete"}:
        return "<span class='ok'>completed</span>"
    if status in {"fallback", "needs_review", "not_run"}:
        return "<span class='warn'>warning</span>"
    if status in {"failed", "error"}:
        return "<span class='bad'>failed</span>"
    return f"<span class='warn'>{status}</span>"


def _pct(value: Any) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "n/a"


def _style() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f7f8f5; color: #1f2a24; }
        .moose-card {
            border: 1px solid #d6ddd2;
            border-radius: 8px;
            padding: 14px 16px;
            margin: 8px 0;
            background: #ffffff;
            min-height: 72px;
        }
        .moose-card span { color: #5c6b61; font-size: 0.86rem; }
        .moose-card strong { color: #163225; }
        .ok, .warn, .bad {
            border-radius: 999px;
            padding: 2px 8px;
            font-size: 0.75rem;
            margin-right: 4px;
        }
        .ok { background: #dceee3; color: #16452d; }
        .warn { background: #fff1c7; color: #5c4300; }
        .bad { background: #ffd8d0; color: #702616; }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
