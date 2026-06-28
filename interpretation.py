"""
interpretation.py — the Investment Read (interpretation layer).

GPT narrates investment judgment from a structured FACT SHEET it cannot contradict;
it never computes numbers or reads raw cells. Three trust tiers feed it:
  T1 validated   — spine / deal_truth / deal_analysis / perf-vs-plan (bulletproof)
  T2 components  — the roll-up's foot-validated revenue/opex leaves (high)
  T3 labeled     — raw-cell reads, flagged low-confidence (off the roll-up)

This file (Phase 1+2) is the DETERMINISTIC assembler: it builds the fact sheet,
classifies the deal archetype, and detects the read mode. The GPT call (Phase 5)
consumes `assemble_fact_sheet(...)` — it is not wired here yet.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

FACT_SHEET_VERSION = "2026-06-28.1"


# ---------------------------------------------------------------------------
# Archetype — deterministic signals -> provisional label + behaviour lens.
# (GPT later confirms at the fuzzy boundary; the lens anchors the judgment.)
# ---------------------------------------------------------------------------
_ARCHETYPE_LENS = {
    "opportunistic / development": (
        "Returns are deeply back-loaded; early NOI is expected near zero (build + "
        "lease-up). An early NOI miss is meaningless unless lease-up pace or delivery "
        "timeline slips — watch absorption, not in-place NOI."),
    "value-add": (
        "The value engine is the rent jump from repositioning. An NOI miss matters if "
        "rents/occupancy aren't responding to capex (thesis failing); it's tolerable if "
        "it's timing. Revenue ahead = thesis landing; a cost overrun is execution risk."),
    "core-plus": (
        "Mostly stabilized with a thin upside lever (inflation-plus rent growth). A miss "
        "eats the modest premium quickly — less cushion than value-add."),
    "core": (
        "Flat NOI, no ramp, no cushion — in-place yield is the thesis. Any meaningful NOI "
        "miss is direct and concerning; stability itself is what's being underwritten."),
}


def _classify_archetype(dt: dict, traj: dict) -> dict[str, Any]:
    can = dt.get("canonical", {})
    noi = traj.get("noi") or {}
    gi, stab = noi.get("going_in"), noi.get("stabilized")
    pct = (gi / stab) if (isinstance(gi, (int, float)) and stab) else None
    growth = (stab / gi - 1) if (gi and stab) else None
    cost = (can.get("total_cost") or {}).get("value")
    capex_by_year = (traj.get("capex") or {}).get("by_year") or {}
    capex_total = sum(abs(v) for v in capex_by_year.values()) or None
    capex_int = (capex_total / cost) if (capex_total and cost) else None
    rate = (dt.get("rate_type") or {}).get("type")

    # Classify on HOLD-PERIOD BEHAVIOR (going-in NOI % of stabilized + growth) — that
    # is what the "how to read a miss" lens needs. deal_type (acquisition strategy) is
    # context, NOT an override: it over-applies "development" and describes history, not
    # how NOI moves during the hold. When the two disagree, confidence drops to medium
    # and GPT refines at the boundary.
    if pct is None:
        label, conf = "unknown", "low"
    elif pct < 0.30:
        label, conf = "opportunistic / development", "high"
    elif pct < 0.80:
        label, conf = "value-add", "high" if pct < 0.72 else "medium"
    elif pct < 0.92:
        label, conf = "core-plus", "medium"
    else:
        label, conf = "core", "high"

    deal_type = (dt.get("deal_type") or "").lower()
    strategy_conflict = (deal_type == "development" and label in ("core", "core-plus"))
    if strategy_conflict:
        conf = "medium"          # behaves flat, but underwritten as development — flag it

    signals = {
        "going_in_noi_pct_of_stabilized": round(pct, 3) if pct is not None else None,
        "noi_growth": round(growth, 3) if growth is not None else None,
        "capex_intensity": round(capex_int, 3) if capex_int is not None else None,
        "financing": rate, "deal_type": deal_type or None,
    }
    return {"label": label, "confidence": conf, "signals": signals,
            "strategy_conflict": strategy_conflict, "lens": _ARCHETYPE_LENS.get(label, "")}


# ---------------------------------------------------------------------------
# Claims — the load-bearing conclusions, computed deterministically. GPT narrates
# these; it never derives them. Each: {id, headline, what_changed, why,
# why_matters, implication, direction, confidence, sources, guardrail}.
# ---------------------------------------------------------------------------
_NOI_VARIANCE_GATE = 0.03   # below this, NOI is "tracking" — don't dissect drivers


def _k(v):
    return f"${abs(v)/1e3:,.0f}K" if abs(v) < 1e6 else f"${abs(v)/1e6:.1f}M"


def _performance_claims(fs: dict, perf: dict) -> list[dict]:
    var = perf.get("variance") or {}
    items = perf.get("items") or {}
    noi_pct, noi_delta = var.get("pct"), var.get("delta")
    months = var.get("n")
    conf = (f"{months}-mo: early signal" if (months and months < 6)
            else f"{months}-mo trend" if months else "—")
    lens = fs["deal"]["archetype"].get("lens", "")
    claims: list[dict] = []

    # gap_driver — GATED on the NOI variance (user rule: >3% -> read rev & exp).
    if isinstance(noi_pct, (int, float)) and abs(noi_pct) <= _NOI_VARIANCE_GATE:
        claims.append({
            "id": "gap_driver", "direction": "on_plan", "confidence": conf,
            "headline": "NOI is tracking to plan",
            "what_changed": f"NOI is within {int(_NOI_VARIANCE_GATE*100)}% of plan "
                            f"({noi_pct*100:+.1f}%).",
            "why": "No material variance to dissect.", "why_matters": "",
            "implication": "", "sources": ["variance"],
            "guardrail": f"NOI is on plan ({noi_pct*100:+.1f}%); do not over-dramatize a "
                         "small variance."})
    elif isinstance(noi_pct, (int, float)):
        opex_delta = items.get("opex_delta") or 0                     # +ve = opex OVER plan
        rev_delta = items.get("revenue_delta")
        rev_dom = (rev_delta is not None and abs(rev_delta) > abs(opex_delta))
        direction = "revenue" if rev_dom else "expense"
        rev_ahead = (rev_delta or 0) >= 0
        movers = (items.get("movers") or [])[:3]
        mv = "; ".join(f"{it['label']} {'+' if it['delta'] > 0 else '−'}{_k(it['delta'])}"
                       for it in movers)
        below = noi_pct < 0
        claims.append({
            "id": "gap_driver", "direction": direction, "confidence": conf,
            "headline": f"NOI is {abs(noi_pct)*100:.1f}% {'below' if below else 'above'} "
                        f"plan — {direction}-driven",
            "what_changed": f"NOI is {abs(noi_pct)*100:.1f}% {'below' if below else 'above'} plan.",
            "why": (f"Revenue is {'+' if rev_ahead else '−'}{_k(rev_delta or 0)} vs plan; "
                    f"opex is {'+' if opex_delta >= 0 else '−'}{_k(opex_delta)} vs plan — "
                    f"the gap is {direction}-driven."),
            "why_matters": lens,
            "implication": f"Movers: {mv}." if mv else "",
            "sources": ["variance", "items"],
            "guardrail": (f"The NOI gap is {direction.upper()}-driven; revenue is "
                          f"{'AHEAD of' if rev_ahead else 'BEHIND'} plan. Do not attribute the "
                          f"gap to {'expenses' if direction == 'revenue' else 'revenue'}.")})

    # returns_resilient
    lev = next((r for r in (perf.get("returns") or []) if r["leg"] == "levered"
                and r.get("blended_irr") is not None), None)
    if lev:
        bps = round((lev["blended_irr"] - lev["projected_irr"]) * 10000)
        claims.append({
            "id": "returns_resilient", "direction": "down" if bps < 0 else "up",
            "confidence": conf,
            "headline": f"Levered IRR tracking {lev['blended_irr']*100:.2f}% "
                        f"(underwritten {lev['projected_irr']*100:.2f}%)",
            "what_changed": f"Levered IRR {lev['projected_irr']*100:.2f}% → "
                            f"{lev['blended_irr']*100:.2f}% ({bps:+d} bps).",
            "why": f"Only the {months or 0} elapsed months reflect actuals; the rest of the "
                   "plan is held unchanged (capex & financing at plan).",
            "why_matters": "Realized impact is modest; the cushion erodes if the variance "
                           "persists into stabilization.",
            "implication": "", "sources": ["returns"],
            "guardrail": f"Levered IRR is tracking {'DOWN' if bps < 0 else 'UP'} "
                         f"({lev['projected_irr']*100:.2f}% → {lev['blended_irr']*100:.2f}%); "
                         f"do not say returns {'improved' if bps < 0 else 'declined'}."})
    return claims


def _acquisition_claims(fs: dict) -> list[dict]:
    a = fs["deal"]["archetype"]
    t = fs["deal"]["targets"]
    nb = t["noi_bridge"]
    claims: list[dict] = []

    def pct(v):
        return f"{v*100:.1f}%" if isinstance(v, (int, float)) else "—"

    def m(v):
        return _k(v) if isinstance(v, (int, float)) else "—"

    # thesis
    growth = a["signals"].get("noi_growth")
    claims.append({
        "id": "thesis", "direction": a["label"], "confidence": a["confidence"],
        "headline": f"{a['label'].title()} — NOI {m(nb['going_in'])} → {m(nb['stabilized'])}"
                    + (f" ({growth*100:+.0f}%)" if isinstance(growth, (int, float)) else ""),
        "what_changed": "", "why": a["lens"],
        "why_matters": (f"Going-in NOI is {a['signals'].get('going_in_noi_pct_of_stabilized', '?')} "
                        "of stabilized — the value to be created is the ramp."),
        "implication": (f"Underwritten exit {m(t['sale_price'])} at a {pct(t['exit_cap'])} cap."),
        "sources": ["archetype", "noi_bridge"],
        "guardrail": (f"Read this as a {a['label']} deal (lens above)."
                      + (" Note: underwritten as development but hold-period NOI is flat — "
                         "flag the strategy/behaviour mismatch." if a.get("strategy_conflict") else ""))})
    # return_profile
    claims.append({
        "id": "return_profile", "direction": "", "confidence": "T1",
        "headline": f"Levered IRR {pct(t['levered_irr'])} · EM {t.get('levered_em')}",
        "what_changed": "", "why": f"Unlevered {pct(t['unlevered_irr'])}; LTC {pct(t['ltc'])}.",
        "why_matters": "", "implication": "", "sources": ["targets"], "guardrail": ""})
    # structural_risk — from rate + leverage + lens
    fin = fs["deal"]["strategy"]["financing"]
    if fin == "floating":
        claims.append({
            "id": "structural_risk", "direction": "rate", "confidence": "T1",
            "headline": "Floating-rate exposure",
            "what_changed": "", "why": "Levered return rides the rate path; "
                            f"floor {pct(fs['deal']['strategy']['rate'].get('floor'))}.",
            "why_matters": "A NOI shortfall compresses DSCR headroom; with floating debt a "
                           "higher-rate environment compounds it.",
            "implication": "", "sources": ["rate_type"],
            "guardrail": "Financing is FLOATING; do not assume fixed-rate."})
    return claims


def build_claims(fs: dict, perf: dict | None = None) -> list[dict]:
    if fs.get("mode") == "performance" and perf:
        return _performance_claims(fs, perf)
    return _acquisition_claims(fs)


# ---------------------------------------------------------------------------
# Fact-sheet assembly (deterministic — no GPT).
# ---------------------------------------------------------------------------
def _v(can: dict, c: str):
    return (can.get(c) or {}).get("value")


def _traj_pts(t: dict | None) -> dict | None:
    if not t:
        return None
    return {"going_in": t.get("going_in"), "stabilized": t.get("stabilized"),
            "exit": t.get("exit"), "by_year": t.get("by_year"), "source": t.get("source")}


def assemble_fact_sheet(file_path: str | Path, dt: dict | None = None,
                        analysis: dict | None = None,
                        perf: dict | None = None) -> dict[str, Any]:
    """Aggregate Deal Truth + Deal Analysis + (optional) perf-vs-plan into the one
    structured object the GPT layer consumes. Deterministic; T1 facts + T2 footed
    components + archetype + guardrails + confidence + mode."""
    file_path = Path(file_path)
    if dt is None:
        from deal_truth import build_deal_truth
        dt = build_deal_truth(file_path)
    if not dt.get("engine_found", True):
        return {"ok": False, "reason": dt.get("reason", "cash-flow engine not found"),
                "version": FACT_SHEET_VERSION}
    if analysis is None:
        from deal_analysis import build_analysis
        analysis = build_analysis(file_path, dt=dt)

    can = dt.get("canonical", {})
    traj = analysis.get("traj") or {}
    components = analysis.get("components") or {}
    rate = dt.get("rate_type") or {}
    struct = rate.get("structure") or {}
    hold = dt.get("hold") or {}

    archetype = _classify_archetype(dt, traj)

    deal = {
        "archetype": archetype,
        "strategy": {
            "deal_type": dt.get("deal_type"),
            "hold": {"months": hold.get("months"), "years": hold.get("years")},
            "financing": rate.get("type"),
            "rate": {"spread": (struct.get("spread") or {}).get("value"),
                     "floor": (struct.get("floor") or {}).get("value")},
        },
        "targets": {
            "levered_irr": _v(can, "levered_irr"), "unlevered_irr": _v(can, "unlevered_irr"),
            "levered_em": _v(can, "equity_multiple"),
            "noi_bridge": {"going_in": (traj.get("noi") or {}).get("going_in"),
                           "stabilized": (traj.get("noi") or {}).get("stabilized"),
                           "exit": (traj.get("noi") or {}).get("exit")},
            "going_in_cap": _v(can, "going_in_cap"), "exit_cap": _v(can, "exit_cap"),
            "sale_price": _v(can, "sale_price"), "yield_on_cost": _v(can, "yield_on_cost"),
            "total_cost": _v(can, "total_cost"), "debt": _v(can, "debt"),
            "equity": _v(can, "equity"), "ltv": _v(can, "ltv"), "ltc": _v(can, "ltc"),
        },
    }

    operating = {c: _traj_pts(traj.get(c)) for c in ("noi", "revenue", "opex", "capex")}
    operating["components"] = {
        c: {"total": d["total"], "footed": d["footed"],
            "components": [{"label": x["label"], "stabilized": x["stabilized"],
                            "going_in": x["going_in"], "share": x["share"],
                            "source": x["source"]} for x in d["components"]]}
        for c, d in components.items()
    }

    mode = "performance" if (perf and perf.get("ok")) else "acquisition"
    performance = None
    if mode == "performance":
        var = perf.get("variance") or {}
        rets = {r["leg"]: r for r in (perf.get("returns") or [])}
        performance = {
            "as_of_months": var.get("n"),
            "noi_variance_pct": var.get("pct"),
            "blended_returns": {leg: {"projected_irr": r.get("projected_irr"),
                                      "blended_irr": r.get("blended_irr"),
                                      "projected_em": r.get("projected_em"),
                                      "blended_em": r.get("blended_em")}
                                for leg, r in rets.items()},
            "definition_match": (perf.get("definition_match") or {}).get("verdict"),
            "line_items": perf.get("items"),
        }

    # Guardrails — but DROP the source-conflict rails for concepts the validated
    # trajectory / rate-structure supersedes: those rails name the broken point-fact
    # as the "winner" (e.g. noi=$65,793, interest_rate=0) and would re-inject the very
    # values the trajectory replaced. Keep all other guardrails (debt, exit, floating).
    import re as _re
    _superseded = _re.compile(
        r"disagree on (noi|revenue|opex|operating expense|capex|interest)", _re.I)
    guardrails = [g["message"] for g in (dt.get("guardrails") or [])
                  if g.get("message") and not _superseded.search(g["message"])]

    confidence = {
        "data_coverage": {"noi": "T1", "opex_components":
                          ("T2-footed" if (components.get("opex") or {}).get("footed") else "T2-unfooted"),
                          "revenue_components":
                          ("T2-footed" if (components.get("revenue") or {}).get("footed") else "T2-unfooted")},
        "definition_match": (perf.get("definition_match") or {}).get("verdict") if perf else None,
        "months_of_actuals": (perf.get("variance") or {}).get("n") if perf else None,
    }

    fs = {"ok": True, "version": FACT_SHEET_VERSION, "mode": mode,
          "deal": deal, "operating": operating, "performance": performance,
          "guardrails": guardrails, "confidence": confidence}
    # Claims (computed) + their derived guardrails — the binding layer GPT obeys.
    fs["claims"] = build_claims(fs, perf)
    fs["guardrails"] = guardrails + [c["guardrail"] for c in fs["claims"] if c.get("guardrail")]
    return fs


# ---------------------------------------------------------------------------
# Human-readable dump (for review — not the GPT prompt).
# ---------------------------------------------------------------------------
def render_fact_sheet(fs: dict) -> str:
    if not fs.get("ok"):
        return f"(fact sheet unavailable: {fs.get('reason')})"

    def M(v):
        return f"${v/1e6:.1f}M" if isinstance(v, (int, float)) and abs(v) >= 1e6 else (
            f"${v/1e3:.0f}K" if isinstance(v, (int, float)) and abs(v) >= 1e3 else (
                f"${v:,.0f}" if isinstance(v, (int, float)) else "—"))

    def P(v):
        return f"{v*100:.1f}%" if isinstance(v, (int, float)) else "—"

    L = [f"FACT SHEET  ·  mode={fs['mode']}  ·  v{fs['version']}", ""]
    a = fs["deal"]["archetype"]
    L.append(f"ARCHETYPE: {a['label']} ({a['confidence']} confidence)")
    L.append(f"  signals: {a['signals']}")
    s, t = fs["deal"]["strategy"], fs["deal"]["targets"]
    L.append(f"STRATEGY: {s['deal_type']} · hold {s['hold']['months']} mo · {s['financing']}"
             f" (spread {P(s['rate']['spread'])}, floor {P(s['rate']['floor'])})")
    L.append(f"TARGETS:  levered IRR {P(t['levered_irr'])} · EM {t['levered_em']} · "
             f"exit {M(t['sale_price'])} @ {P(t['exit_cap'])} cap")
    nb = t["noi_bridge"]
    L.append(f"  NOI bridge: {M(nb['going_in'])} -> {M(nb['stabilized'])} -> {M(nb['exit'])} exit")
    L.append(f"  cost {M(t['total_cost'])} · debt {M(t['debt'])} · equity {M(t['equity'])} · LTC {P(t['ltc'])}")
    comps = fs["operating"]["components"]
    for c in ("opex", "revenue"):
        cc = comps.get(c)
        if not cc:
            continue
        flag = "FOOTED" if cc["footed"] else "unfooted (not asserted)"
        L.append(f"{c.upper()} COMPONENTS [{flag}] total {M(cc['total'])}:")
        for x in cc["components"][:6]:
            L.append(f"    {x['label'][:32]:<32} {M(x['stabilized'])} ({P(x['share'])})")
    if fs["performance"]:
        pf = fs["performance"]
        L.append(f"PERFORMANCE: {pf['as_of_months']} mo · NOI {P(pf['noi_variance_pct'])} vs plan"
                 f" · def-match {pf['definition_match']}")
    L.append("")
    L.append(f"CLAIMS ({len(fs.get('claims', []))}):")
    for cl in fs.get("claims", []):
        L.append(f"  [{cl['id']}] {cl['headline']}  ({cl.get('confidence', '')})")
        if cl.get("why"):
            L.append(f"      why: {cl['why']}")
        if cl.get("implication"):
            L.append(f"      → {cl['implication']}")
    if fs["guardrails"]:
        L.append("GUARDRAILS:")
        for g in fs["guardrails"][:6]:
            L.append(f"    - {g[:100]}")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# The Investment Read — GPT narrates the fact sheet (Phase 5). GPT writes prose
# only; the claims/numbers are pre-computed and binding. Deterministic fallback
# when no API key, so it always renders (like deal_analysis).
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are an experienced real-estate asset manager writing the opening of an investment-
committee memo. You are given a VALIDATED Fact Sheet (every number is already correct),
a set of computed CLAIMS, and binding GUARDRAILS. Your job is to turn them into a concise
investment READ — what this is, what changed, why, what deserves attention, what's next.

HARD RULES (a violation makes the read worthless):
1. Narrate ONLY from the Fact Sheet and Claims. NEVER invent, recompute, or alter a number.
2. Obey EVERY guardrail. Never contradict one. They override your instincts.
3. The Claims are your findings — do not flip an attribution or change a direction. Explain them.
4. Apply the archetype lens when judging whether something is concerning or expected.
5. Write investment prose, not a metric list. Tight. An analyst's voice, not a dashboard.
6. Recommendations are JUDGMENT — phrase them as such, proportional to the issue.
7. If mode is "acquisition" there are no actuals — do NOT discuss "what changed" or performance.

OUTPUT — exactly these three sections, markdown headers:
## Investment Snapshot
   One short paragraph: the deal, its archetype, and where it sits in the business plan.
## Key Investment Findings
   3–5 bullets, each an evidence-backed observation drawn from the Claims (what changed / why it
   matters). Lead with the most important.
## Attention & Recommendations
   1–2 issues that most affect future performance or risk, then 1–2 practical next steps.
"""


def _prompt_payload(fs: dict) -> str:
    import json
    lines = [f"MODE: {fs['mode']}", "", "FACT SHEET (validated — do not alter):",
             render_fact_sheet(fs), "", "CLAIMS (your findings — explain, do not change):"]
    for c in fs.get("claims", []):
        lines.append(json.dumps({k: c[k] for k in
                     ("id", "headline", "what_changed", "why", "why_matters", "implication",
                      "direction", "confidence") if c.get(k)}, default=str))
    lines += ["", "GUARDRAILS (binding — never contradict):"]
    lines += [f"- {g}" for g in fs.get("guardrails", [])]
    return "\n".join(lines)


def _deterministic_read(fs: dict) -> str:
    a = fs["deal"]["archetype"]
    out = ["## Investment Snapshot",
           f"{a['label'].title()} deal ({a['confidence']} confidence). {a.get('lens','')}",
           "", "## Key Investment Findings"]
    for c in fs.get("claims", []):
        out.append(f"- **{c['headline']}** — {c.get('why','')}"
                   + (f" {c['implication']}" if c.get("implication") else ""))
    out += ["", "## Attention & Recommendations",
            "_(Narrative read requires an API key; showing the computed findings above.)_"]
    return "\n".join(out)


def build_investment_read(file_path, dt=None, analysis=None, perf=None) -> dict[str, Any]:
    """The Investment Read artifact. Assembles the fact sheet, then GPT narrates it
    under the binding guardrails (deterministic fallback when no key)."""
    fs = assemble_fact_sheet(file_path, dt=dt, analysis=analysis, perf=perf)
    if not fs.get("ok"):
        return {"ok": False, "reason": fs.get("reason"),
                "md": f"> Investment read unavailable: {fs.get('reason')}"}
    from scenarios._llm import llm_available, complete
    if not llm_available():
        return {"ok": True, "source": "deterministic", "fact_sheet": fs,
                "md": _deterministic_read(fs)}
    try:
        md = complete(_SYSTEM_PROMPT, _prompt_payload(fs), temperature=0.2)
    except Exception as e:                                  # pragma: no cover - defensive
        return {"ok": True, "source": "deterministic", "fact_sheet": fs,
                "md": _deterministic_read(fs), "note": f"{type(e).__name__}: {e}"}
    return {"ok": True, "source": "gpt", "fact_sheet": fs, "md": md}


if __name__ == "__main__":
    import sys
    print(render_fact_sheet(assemble_fact_sheet(sys.argv[1])))
