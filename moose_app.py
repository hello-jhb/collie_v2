"""Moose Streamlit prototype.

Run with:
    streamlit run moose_app.py
"""

from __future__ import annotations

import tempfile
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from moose.pipeline import run_financial_model_reasoning


SNAPSHOT_METRICS = [
    ("purchase_price", "Purchase Price"),
    ("total_project_cost", "Total Project Cost"),
    ("debt_amount", "Debt"),
    ("equity_required", "Equity"),
    ("loan_to_value", "LTV"),
    ("interest_rate", "Interest Rate"),
    ("stabilized_noi", "NOI"),
    ("levered_irr", "Levered IRR"),
    ("equity_multiple", "Equity Multiple"),
    ("exit_cap_rate", "Exit Cap"),
    ("sale_value", "Sale Value"),
]

READ_SECTIONS = [
    "Capital Structure",
    "Return Profile",
    "Operating / NOI Read",
    "Exit Assumptions",
    "Items Requiring Review",
]


def main() -> None:
    st.set_page_config(page_title="Moose", page_icon="M", layout="wide")
    _style()

    st.title("Moose")
    st.caption("Agent-centric workbook understanding, code-grounded verification, and transparent investment readouts.")

    with st.sidebar:
        st.header("Upload")
        uploaded = st.file_uploader("Excel workbook", type=["xlsx", "xlsm", "xltx", "xltm"])
        run_clicked = st.button("Analyze Model", type="primary", use_container_width=True)
        st.divider()
        st.caption("LLM calls use OPENAI_API_KEY or Streamlit secrets. Moose reports any fallback usage clearly.")

    if not run_clicked:
        _empty_state()
        return

    try:
        workbook_path, display_name = _resolve_workbook(uploaded)
    except ValueError as exc:
        st.error(str(exc))
        return

    with st.status("Analyzing model...", expanded=False) as status:
        try:
            result = run_financial_model_reasoning(workbook_path)
        except Exception as exc:
            status.update(label="Analysis failed", state="error")
            st.error(f"Moose could not process this workbook: {type(exc).__name__}: {exc}")
            return
        status.update(label="Analysis complete", state="complete")

    _render_results(display_name, result)


def _resolve_workbook(uploaded: Any) -> tuple[Path, str]:
    if uploaded is not None:
        suffix = Path(uploaded.name).suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(uploaded.getbuffer())
            return Path(handle.name), uploaded.name
    raise ValueError("Upload an Excel workbook to run Moose.")


def _render_results(display_name: str, result: dict[str, Any]) -> None:
    verification_run = result["verification_run"]
    claim_result = verification_run["claim_result"]
    verification = verification_run["verification"]
    reasoning = result["reasoning"]
    intake = claim_result.get("intake_result", {})
    document_identity = intake.get("document_identity", {})
    orientation = claim_result.get("workbook_orientation", {})
    facts = verification.get("verified_facts", [])

    _render_top_summary(
        display_name=display_name,
        document_identity=document_identity,
        orientation=orientation,
        verification=verification,
        facts=facts,
        claim_result=claim_result,
    )
    _render_deal_snapshot(facts)
    _render_investment_read(reasoning, facts)
    _render_facts(facts, claim_result)
    _render_caveats(verification)
    _render_diagnostics(claim_result, verification_run, reasoning)


def _render_top_summary(
    display_name: str,
    document_identity: dict[str, Any],
    orientation: dict[str, Any],
    verification: dict[str, Any],
    facts: list[dict[str, Any]],
    claim_result: dict[str, Any],
) -> None:
    summary = verification.get("summary", {})
    usable_count = summary.get("verified", 0) + summary.get("verified_with_caveat", 0)
    fallback_count = sum(1 for fact in facts if fact.get("fact_origin") == "fallback")
    verification_status = _verification_status(summary)
    fallback_text = "No fallback facts used." if fallback_count == 0 else f"{fallback_count} fallback-derived fact(s) used."
    workbook_type = _titleize(orientation.get("workbook_type") or document_identity.get("document_type") or "workbook")
    purpose = orientation.get("likely_purpose") or "Analyze the uploaded workbook for investment evidence."

    st.markdown(
        f"""
        <div class="summary-card">
          <div class="summary-kicker">{escape(display_name)}</div>
          <h2>{escape(workbook_type)}</h2>
          <p>{escape(purpose)}</p>
          <p class="summary-read">{escape(_top_read_sentence(workbook_type, usable_count, summary))}</p>
          <div class="summary-grid">
            <div><span>File type</span><strong>{escape(str(document_identity.get("document_type", "unknown")))}</strong></div>
            <div><span>Confidence</span><strong>{escape(_pct(document_identity.get("confidence")))}</strong></div>
            <div><span>Verification</span><strong>{escape(verification_status)}</strong></div>
            <div><span>Fallback</span><strong>{escape(fallback_text)}</strong></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if claim_result.get("extraction_mode"):
        st.caption(f"Extraction mode: {claim_result.get('extraction_mode')}")


def _render_deal_snapshot(facts: list[dict[str, Any]]) -> None:
    st.subheader("Deal Snapshot")
    facts_by_metric = _facts_by_metric(facts)
    for row_start in range(0, len(SNAPSHOT_METRICS), 4):
        cols = st.columns(4)
        for col, (metric, label) in zip(cols, SNAPSHOT_METRICS[row_start:row_start + 4]):
            fact = facts_by_metric.get(metric)
            with col:
                _snapshot_card(label, fact)


def _render_investment_read(reasoning: dict[str, Any], facts: list[dict[str, Any]]) -> None:
    st.subheader("Investment Read")
    summary = reasoning.get("answer_summary") or _fallback_answer_summary(facts)
    st.markdown(
        f"<div class='moose-card read-card'><strong>Executive Read</strong><br>{escape(str(summary))}</div>",
        unsafe_allow_html=True,
    )
    sections = reasoning.get("sections") or _fallback_read_sections(facts)
    for row_start in range(0, len(READ_SECTIONS), 2):
        cols = st.columns(2)
        for col, title in zip(cols, READ_SECTIONS[row_start:row_start + 2]):
            body = sections.get(title) or "No verified fact is available for this section yet."
            with col:
                st.markdown(
                    f"<div class='moose-card read-card'><strong>{escape(title)}</strong><br>{escape(str(body))}</div>",
                    unsafe_allow_html=True,
                )


def _render_facts(facts: list[dict[str, Any]], claim_result: dict[str, Any]) -> None:
    st.subheader("Verified Facts")
    gpt = [fact for fact in facts if fact.get("fact_origin") == "gpt_native"]
    fallback = [fact for fact in facts if fact.get("fact_origin") == "fallback"]
    st.caption(
        f"{len(facts)} verified or reviewed facts returned. "
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
    st.subheader("Caveats / Trust")
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
    for fact in facts:
        with st.expander(f"{fact.get('metric_or_subject')} | {fact.get('source')} | {fact.get('verification_status')}"):
            st.write("Checks")
            st.dataframe(pd.DataFrame(fact.get("checks", [])), use_container_width=True, hide_index=True)
            st.write("Caveats")
            st.write(fact.get("caveats", []))


def _render_diagnostics(claim_result: dict[str, Any], verification_run: dict[str, Any], reasoning: dict[str, Any]) -> None:
    st.subheader("Diagnostics")
    diagnostics = verification_run.get("diagnostics", {})
    with st.expander("Intake"):
        st.json(claim_result.get("intake_result", {}))
    with st.expander("Mental Model"):
        st.json(claim_result.get("mental_model", {}))
    with st.expander("Evidence Pack"):
        st.json(diagnostics.get("evidence_pack", {}))
    with st.expander("Claim Discovery"):
        st.json({
            "mode": claim_result.get("extraction_mode"),
            "comparison": claim_result.get("discovery_comparison", {}),
            "diagnostics": diagnostics.get("claim_discovery", {}),
        })
    with st.expander("Grounding"):
        st.json(diagnostics.get("grounding", {}))
    with st.expander("Trust Engine"):
        st.json(diagnostics.get("verification", {}))
        _render_evidence(verification_run.get("verification", {}).get("verified_facts", []))
    with st.expander("Reconciliation"):
        st.json({
            "diagnostics": diagnostics.get("reconciliation", {}),
            "notes": verification_run.get("verification", {}).get("reconciliation_notes", []),
        })
    with st.expander("Reasoning"):
        st.json(reasoning)


def _empty_state() -> None:
    st.info("Upload an Excel workbook to analyze the model.")


def _snapshot_card(label: str, fact: dict[str, Any] | None) -> None:
    if not fact:
        st.markdown(
            f"""
            <div class='metric-card missing'>
              <span>{escape(label)}</span>
              <strong>Not found</strong>
              <small>No verified source yet</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f"""
        <div class='metric-card'>
          <span>{escape(label)}</span>
          <strong>{escape(_format_fact_value(fact))}</strong>
          <small>{_status_badge(str(fact.get("verification_status")))} {escape(str(fact.get("source", "unknown")))}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _facts_by_metric(facts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(fact.get("metric_or_subject")): fact
        for fact in facts
        if fact.get("metric_or_subject") and fact.get("verification_status") in {"verified", "verified_with_caveat"}
    }


def _format_fact_value(fact: dict[str, Any]) -> str:
    value = fact.get("verified_value")
    unit = fact.get("unit")
    if value is None:
        return "Not verified"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if unit == "currency":
            return f"${value:,.0f}"
        if unit == "percent":
            return f"{value:.2%}" if abs(value) <= 1 else f"{value:.2f}%"
        if unit == "multiple":
            return f"{value:.2f}x"
        return f"{value:,.2f}"
    return str(value)


def _fallback_answer_summary(facts: list[dict[str, Any]]) -> str:
    usable = [fact for fact in facts if fact.get("verification_status") in {"verified", "verified_with_caveat"}]
    if not usable:
        return "Moose did not find verified investment facts in this workbook yet."
    return f"Moose identified {len(usable)} investment fact(s) that passed verification or were verified with caveats."


def _fallback_read_sections(facts: list[dict[str, Any]]) -> dict[str, str]:
    fact_map = _facts_by_metric(facts)

    def line(metric: str, label: str) -> str:
        fact = fact_map.get(metric)
        if not fact:
            return f"{label}: not found."
        return f"{label}: {_format_fact_value(fact)} from {fact.get('source')}."

    caveated = [fact.get("metric_or_subject") for fact in facts if fact.get("verification_status") == "verified_with_caveat"]
    return {
        "Capital Structure": " ".join([
            line("total_project_cost", "Total project cost"),
            line("debt_amount", "Debt"),
            line("equity_required", "Equity"),
            line("loan_to_value", "LTV"),
        ]),
        "Return Profile": " ".join([
            line("levered_irr", "Levered IRR"),
            line("equity_multiple", "Equity multiple"),
        ]),
        "Operating / NOI Read": line("stabilized_noi", "NOI"),
        "Exit Assumptions": " ".join([
            line("exit_cap_rate", "Exit cap"),
            line("sale_value", "Sale value"),
        ]),
        "Items Requiring Review": (
            "Caveated facts: " + ", ".join(str(item) for item in caveated)
            if caveated else "No caveated facts surfaced in this run."
        ),
    }


def _verification_status(summary: dict[str, Any]) -> str:
    total = int(summary.get("claims_total", 0) or 0)
    rejected = int(summary.get("rejected", 0) or 0)
    contradicted = int(summary.get("contradicted", 0) or 0)
    needs_review = int(summary.get("needs_review", 0) or 0)
    caveated = int(summary.get("verified_with_caveat", 0) or 0)
    verified = int(summary.get("verified", 0) or 0)
    if total == 0:
        return "No facts verified"
    if rejected or contradicted:
        return "Issues found"
    if needs_review:
        return "Needs review"
    if caveated and not verified:
        return "Verified with caveats"
    if caveated:
        return "Partially caveated"
    return "Verified"


def _top_read_sentence(workbook_type: str, usable_count: int, summary: dict[str, Any]) -> str:
    status = _verification_status(summary).lower()
    if usable_count == 0:
        return f"This appears to be a {workbook_type}. Moose did not verify core investment facts yet."
    return f"This appears to be a {workbook_type}. Moose identified {usable_count} investment fact(s) and marked the verification status as {status}."


def _titleize(value: Any) -> str:
    return str(value or "Workbook").replace("_", " ").title()


def _status_badge(status: str) -> str:
    labels = {
        "passed": ("ok", "passed"),
        "complete": ("ok", "complete"),
        "verified": ("ok", "verified"),
        "verified_with_caveat": ("warn", "caveated"),
        "fallback": ("warn", "fallback"),
        "needs_review": ("warn", "review"),
        "not_run": ("warn", "not run"),
        "contradicted": ("bad", "contradicted"),
        "rejected": ("bad", "rejected"),
        "failed": ("bad", "failed"),
        "error": ("bad", "error"),
    }
    css_class, label = labels.get(status, ("warn", status.replace("_", " ")))
    return f"<span class='{css_class}'>{escape(label)}</span>"


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
        .summary-card {
            background: #ffffff;
            border: 1px solid #d6ddd2;
            border-radius: 8px;
            padding: 22px 24px;
            margin: 8px 0 18px 0;
        }
        .summary-card h2 { margin: 4px 0 8px 0; color: #163225; }
        .summary-card p { margin: 0 0 10px 0; color: #33433a; }
        .summary-kicker { color: #627166; font-size: 0.86rem; }
        .summary-read { font-size: 1.02rem; }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-top: 14px;
        }
        .summary-grid div {
            border-top: 1px solid #e3e8e0;
            padding-top: 10px;
        }
        .summary-grid span, .metric-card span {
            display: block;
            color: #5c6b61;
            font-size: 0.82rem;
        }
        .summary-grid strong { color: #163225; font-size: 0.96rem; }
        .moose-card {
            border: 1px solid #d6ddd2;
            border-radius: 8px;
            padding: 14px 16px;
            margin: 8px 0;
            background: #ffffff;
            min-height: 72px;
        }
        .metric-card {
            border: 1px solid #d6ddd2;
            border-radius: 8px;
            padding: 14px 16px;
            margin: 8px 0;
            background: #ffffff;
            min-height: 118px;
        }
        .metric-card strong {
            display: block;
            color: #163225;
            font-size: 1.25rem;
            margin-top: 4px;
            overflow-wrap: anywhere;
        }
        .metric-card small {
            display: block;
            margin-top: 10px;
            color: #5c6b61;
            line-height: 1.35;
        }
        .metric-card.missing { background: #fbfcfa; }
        .read-card { min-height: 112px; line-height: 1.45; }
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
