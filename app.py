"""
app.py — v2 frontend.

Flow:
  1. Landing screen: scenario picker (4 cards, 2 active + 2 "coming soon").
  2. After picking a scenario, scoped chat workspace:
     - "← Back to scenarios" header
     - File uploader (auto-clears previous batch + resets SSOT)
     - Chat thread with the scenario-bound agent
     - SSOT panel in an expander

The agent does all the heavy lifting (classify, ingest, run scenario, answer
follow-ups). This file is just orchestration + presentation.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import ssot
from agent_loop import AgentSession, SCENARIO_CONFIG


# =============================================================================
# Page config & global CSS
# =============================================================================

st.set_page_config(
    page_title="Fantastic Beast & Where to Find Them",
    page_icon="🏢",
    layout="wide",
)

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, .stApp { font-family: "Inter", system-ui, sans-serif; }
  .block-container { padding-top: 2rem; max-width: 1100px; }

  /* Hero */
  .hero-title { font-size: 32px; font-weight: 700; margin-bottom: 4px; }
  .hero-sub   { font-size: 15px; color: #6b7280; margin-bottom: 24px; }

  /* Scenario cards */
  .scenario-card {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px;
    background: #ffffff;
    height: 100%;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .scenario-card.active:hover {
    border-color: #2563eb;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.08);
  }
  .scenario-card.disabled { opacity: 0.55; background: #fafafa; }
  .scenario-card .label {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 2px 8px;
    border-radius: 4px;
    margin-bottom: 12px;
  }
  .scenario-card .label.live    { background: #dcfce7; color: #166534; }
  .scenario-card .label.soon    { background: #f3f4f6; color: #6b7280; }
  .scenario-card .title  { font-size: 18px; font-weight: 600; margin-bottom: 6px; }
  .scenario-card .desc   { font-size: 13px; color: #4b5563; line-height: 1.5; min-height: 56px; }

  /* Scoped workspace header */
  .ws-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 18px; }
  .ws-title  { font-size: 22px; font-weight: 600; }
  .ws-scen   { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.06em; }

  /* SSOT pills */
  .ssot-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    background: #eef2ff;
    color: #3730a3;
    font-size: 11px;
    font-weight: 500;
    margin: 2px 4px 2px 0;
  }

  /* Tool-trace items */
  .tool-trace {
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 11px;
    color: #4b5563;
    margin: 2px 0;
  }
</style>
""",
    unsafe_allow_html=True,
)


# =============================================================================
# Session state
# =============================================================================

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

for key, default in [
    ("active_scenario", None),
    ("agent_session", None),
    ("uploaded_filenames", set()),
    ("last_auto_message", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# =============================================================================
# Helpers
# =============================================================================

def _wipe_uploads_and_reset_ssot() -> None:
    """Clean slate for a new analysis."""
    for p in UPLOAD_DIR.iterdir():
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass
    ssot.reset_ssot()
    st.session_state.uploaded_filenames = set()


def _activate_scenario(scenario_key: str) -> None:
    """User clicked a scenario card — start a fresh session for it."""
    _wipe_uploads_and_reset_ssot()
    st.session_state.active_scenario = scenario_key
    st.session_state.agent_session = AgentSession(scenario_key)
    st.session_state.last_auto_message = None


def _back_to_landing() -> None:
    st.session_state.active_scenario = None
    st.session_state.agent_session = None


def _ssot_panel() -> None:
    """Show what's currently in SSOT."""
    summary = ssot.ssot_summary()
    layers = summary["layers_present"]
    files = summary["ingested_files"]

    if not layers and not files:
        st.caption("No files ingested yet.")
        return

    st.markdown("**Layers in SSOT:**")
    if layers:
        st.markdown(
            " ".join(f'<span class="ssot-pill">{layer}</span>' for layer in layers),
            unsafe_allow_html=True,
        )
    else:
        st.caption("(none)")

    st.markdown("**Files ingested:**")
    if files:
        for f in files:
            st.markdown(f"- {f}")
    else:
        st.caption("(none)")


# =============================================================================
# Landing view — scenario picker
# =============================================================================

def render_landing() -> None:
    st.markdown(
        '<div class="hero-title">Fantastic Beast & Where to Find Them</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="hero-sub">Pick an analysis to start. Each scenario is a '
        'scoped workspace — upload the relevant files and chat with the agent.</div>',
        unsafe_allow_html=True,
    )

    # Card grid: 2 columns x 2 rows
    cards = [
        {
            "key": "deal_review",
            "label": "live",
            "title": "Deal Analysis",
            "desc": "Summarize an acquisition from a single underwriting model. "
                    "Going-in basis, NOI, IRR, exit value, debt terms.",
            "active": True,
        },
        {
            "key": "perf_vs_plan",
            "label": "live",
            "title": "Performance Analysis",
            "desc": "Compare actuals against the underwriting or business plan. "
                    "Year-by-year variance with driver attribution.",
            "active": True,
        },
        {
            "key": "lease_review",
            "label": "soon",
            "title": "Lease Review",
            "desc": "Reconcile tenant-level data between leases and rent rolls. "
                    "Flag discrepancies in term, base rent, escalations.",
            "active": False,
        },
        {
            "key": "debt_analysis",
            "label": "soon",
            "title": "Debt Analysis",
            "desc": "DSCR, debt yield, LTV against loan covenants. "
                    "Refinance and maturity outlook.",
            "active": False,
        },
    ]

    row1 = st.columns(2, gap="medium")
    row2 = st.columns(2, gap="medium")

    for card, col in zip(cards, [*row1, *row2]):
        with col:
            cls = "scenario-card active" if card["active"] else "scenario-card disabled"
            label_cls = "live" if card["active"] else "soon"
            label_text = "Available" if card["active"] else "Coming soon"

            st.markdown(
                f"""
<div class="{cls}">
  <span class="label {label_cls}">{label_text}</span>
  <div class="title">{card['title']}</div>
  <div class="desc">{card['desc']}</div>
</div>
""",
                unsafe_allow_html=True,
            )

            if card["active"]:
                st.button(
                    f"Start →",
                    key=f"start_{card['key']}",
                    on_click=_activate_scenario,
                    args=(card["key"],),
                    use_container_width=True,
                )
            else:
                st.button(
                    "Not available yet",
                    key=f"disabled_{card['key']}",
                    disabled=True,
                    use_container_width=True,
                )


# =============================================================================
# Scenario view — file uploader + chat
# =============================================================================

def render_scenario() -> None:
    scenario_key = st.session_state.active_scenario
    cfg = SCENARIO_CONFIG[scenario_key]
    agent: AgentSession = st.session_state.agent_session

    # Header
    left, right = st.columns([4, 1])
    with left:
        st.markdown(
            f'<div class="ws-header"><div>'
            f'<div class="ws-scen">{cfg["display_name"]}</div>'
            f'<div class="ws-title">Workspace</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.button("← Back to scenarios", on_click=_back_to_landing, use_container_width=True)

    st.divider()

    # File uploader
    uploaded = st.file_uploader(
        "Upload files for this analysis",
        type=["xlsx", "xlsm"],
        accept_multiple_files=True,
        key=f"upload_{scenario_key}",
    )

    # New-batch detection: if the uploader's filenames differ from what we've
    # tracked in this session, save the new ones and queue an auto-message
    # to the agent telling it to ingest them.
    auto_trigger_message: str | None = None

    if uploaded:
        current_names = {f.name for f in uploaded}
        if current_names != st.session_state.uploaded_filenames:
            # Save new files to disk
            new_files = [f for f in uploaded if f.name not in st.session_state.uploaded_filenames]
            for uf in new_files:
                (UPLOAD_DIR / uf.name).write_bytes(uf.getbuffer())

            st.session_state.uploaded_filenames = current_names
            file_list = ", ".join(sorted(current_names))
            auto_trigger_message = (
                f"I have uploaded these files: {file_list}. "
                f"Please ingest them and run the {cfg['display_name']} analysis."
            )

    # SSOT panel
    with st.expander("📂 SSOT — Asset record", expanded=False):
        _ssot_panel()

    st.divider()

    # Chat history
    for m in agent.display_messages():
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # Auto-trigger after file upload (only fires once per new batch)
    if auto_trigger_message and auto_trigger_message != st.session_state.last_auto_message:
        st.session_state.last_auto_message = auto_trigger_message
        with st.chat_message("user"):
            st.markdown(auto_trigger_message)
        with st.chat_message("assistant"):
            with st.spinner("Reading files and running analysis..."):
                reply = agent.send(auto_trigger_message)
            st.markdown(reply)
        _render_tool_trace(agent)

    # User chat input
    user_input = st.chat_input("Ask a question about this analysis...")
    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply = agent.send(user_input)
            st.markdown(reply)
        _render_tool_trace(agent)


def _render_tool_trace(agent: AgentSession) -> None:
    """Show what tools the agent called in its last turn (for transparency)."""
    if not agent.last_tool_calls:
        return
    with st.expander(f"🔧 Tool calls this turn ({len(agent.last_tool_calls)})", expanded=False):
        for tc in agent.last_tool_calls:
            args_preview = ", ".join(f"{k}={v!r}" for k, v in tc["arguments"].items())
            st.markdown(
                f'<div class="tool-trace">→ <b>{tc["name"]}</b>({args_preview})</div>',
                unsafe_allow_html=True,
            )
            result = tc["result"]
            if isinstance(result, dict) and "error" in result:
                st.markdown(f'<div class="tool-trace">  ❌ {result["error"]}</div>', unsafe_allow_html=True)
            elif isinstance(result, dict):
                # Compact summary based on result keys
                preview_keys = [k for k in ("filename", "layer", "metric_count", "layers_now_present",
                                            "files", "ready", "narrative") if k in result]
                if "narrative" in preview_keys:
                    st.markdown('<div class="tool-trace">  ✓ narrative generated</div>', unsafe_allow_html=True)
                else:
                    preview = {k: result[k] for k in preview_keys}
                    st.markdown(f'<div class="tool-trace">  ✓ {preview}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="tool-trace">  ✓ {result}</div>', unsafe_allow_html=True)


# =============================================================================
# Router
# =============================================================================

if st.session_state.active_scenario is None:
    render_landing()
else:
    render_scenario()
