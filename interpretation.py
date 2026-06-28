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

    return {"ok": True, "version": FACT_SHEET_VERSION, "mode": mode,
            "deal": deal, "operating": operating, "performance": performance,
            "guardrails": guardrails, "confidence": confidence}


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
    if fs["guardrails"]:
        L.append("GUARDRAILS:")
        for g in fs["guardrails"][:6]:
            L.append(f"    - {g[:100]}")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    fs = assemble_fact_sheet(sys.argv[1])
    print(render_fact_sheet(fs))
