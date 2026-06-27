"""
deal_analysis.py — ONE integrated, grounded analysis (replaces the four
separate GPT deep-dives).

Capital Structure · Return Profile · Cash Flow / NOI · CapEx — all read from the
validated spine (deal_truth) and the deterministic full-read roll-up
(cashflow_rollup). No GPT extraction, so it ALWAYS loads, and every number is
grounded in the cash-flow model rather than guessed off a truncated sheet.

Units: figures are normalized to full dollars — the spine and roll-up read each
sheet's DECLARED units ("$ in 000s" etc.), and the operating statement is
reconciled to the deal (stabilized NOI / exit_cap ≈ sale) for the few sheets
that don't declare units.

Public:
    build_analysis(file_path) -> {"ok", "md", "sections", "dt"}
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Split floating-rate evidence into the index it floats over vs. its rate cap(s),
# so the structure (index + spread + cap) is shown, not a bare misleading "rate".
_RE_INDEX = re.compile(r"sofr|libor|euribor|bsby|forward curve", re.I)
_RE_CAP = re.compile(r"\bcap\b|cap strike", re.I)


def _money(v) -> str:
    if not isinstance(v, (int, float)):
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"${v/1e9:.2f}B"
    if a >= 1e6:
        return f"${v/1e6:.1f}M"
    if a >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"


def _pct(v) -> str:
    """Format a canonical rate that may be stored as a fraction (0.045) OR already
    as a percent number (4.5). The >1.5 split disambiguates those two forms."""
    if not isinstance(v, (int, float)):
        return "—"
    return f"{v*100:.2f}%" if abs(v) <= 1.5 else f"{v:.2f}%"


def _pctf(v) -> str:
    """Format a value that is ALWAYS a fraction — a computed ratio (growth, margin)
    that can legitimately exceed 1.5 (a 235% growth, a 370% margin). Always ×100,
    so it never gets mistaken for an already-percent number the way _pct would."""
    if not isinstance(v, (int, float)):
        return "—"
    return f"{v*100:.1f}%"


def _x(v) -> str:
    return f"{v:.2f}x" if isinstance(v, (int, float)) else "—"


def _val(can: dict, c: str):
    return float(can[c]["value"]) if c in can else None


def _nearest_pow10(x: float) -> float:
    import math
    return float(10 ** round(math.log10(x))) if x > 0 else 1.0


def _declared_units(t: dict) -> bool:
    """True if the concept's source sheet declared its own units (sheet_scale != 1),
    so it is already in full dollars and must NOT receive the deal anchor scale."""
    return abs(float(t.get("sheet_scale", 1.0)) - 1.0) > 1e-9


def _reconcile_operating_units(traj: dict, can: dict) -> dict:
    """Most sheets declare their units (handled upstream); a few don't. Anchor the
    operating statement to the (full-$) deal: scale so stabilized NOI / exit_cap ≈
    sale price. Reliable now that sale/cap are themselves in full dollars.

    The anchor corrects sheets that DON'T declare units. A concept whose sheet DID
    declare units is already full-$ — re-applying the anchor double-scales it (BAC:
    capex on `Model`, declared $000s, was pushed to billions by the NOI ×1000
    anchor). So gate on declared-units, NOT on which sheet: St Regis revenue/opex
    live on a different *undeclared* sheet than NOI and still need the anchor."""
    noi = traj.get("noi")
    if not (noi and isinstance(noi.get("stabilized"), (int, float))):
        return traj
    ec, sp = _val(can, "exit_cap"), _val(can, "sale_price")
    if not (ec and sp):
        return traj
    cf = ec / 100.0 if ec > 1.5 else ec
    raw = abs(noi["stabilized"])
    if cf <= 0 or raw <= 0:
        return traj
    scale = _nearest_pow10(sp * cf / raw)
    if scale in (1.0,) or scale not in (1e-3, 1e3, 1e6):
        return traj
    out = dict(traj)
    for c in ("noi", "revenue", "opex", "capex", "debt_service"):
        if c in out:
            t = out[c]
            if _declared_units(t):
                continue   # sheet declared its units: already full-$
            t = dict(t)
            for k in ("going_in", "stabilized", "exit"):
                if isinstance(t.get(k), (int, float)):
                    t[k] = t[k] * scale
            t["by_year"] = {y: v * scale for y, v in t["by_year"].items()}
            out[c] = t
    return out


def _src(can: dict, c: str) -> str:
    return f"`{can[c]['source']}`" if c in can and can[c].get("source") else ""


def _line(label: str, value: str, src: str = "", flag: str = "") -> str:
    return f"- **{label}:** {value} {src}{flag}".rstrip()


def build_analysis(file_path: str | Path, dt: dict | None = None) -> dict[str, Any]:
    if dt is None:
        from deal_truth import build_deal_truth
        dt = build_deal_truth(file_path)
    if not dt.get("engine_found", True):
        md = ("### Deal Analysis\n\n> ⚠ **Cash-flow engine not found.** No stream "
              "reproduced the model's stated IRR, so the deal was not reconstructed. "
              + (dt.get("reason") or ""))
        return {"ok": False, "md": md, "sections": {}, "dt": dt}

    can = dt.get("canonical", {})
    sections: dict[str, str] = {}

    # The reconciled, full-$ operating roll-up — computed once and reused for the
    # NOI trajectory, the CapEx line, AND the going-in cap (which must divide a
    # going-in NOI that is in the SAME full-dollar units as total cost).
    try:
        from cashflow_rollup import rollup_model, concept_trajectories
        traj = _reconcile_operating_units(concept_trajectories(rollup_model(file_path)), can)
    except Exception:
        traj = {}

    # --- Capital Structure ------------------------------------------------
    cs = ["#### Capital Structure"]
    for c, lab in (("total_cost", "Total cost"), ("purchase_price", "Acquisition cost"),
                   ("debt", "Debt"), ("equity", "Equity")):
        if c in can:
            cf = " ✅" if can[c].get("cf_validated") else ""
            cs.append(_line(lab, _money(_val(can, c)), _src(can, c), cf))
    rt = dt.get("rate_type") or {}
    is_floating = rt.get("type") == "floating"
    # On floating debt the stored "interest rate" is the SPREAD/margin over the
    # index — there is no single all-in rate (it = index path + spread). Label it
    # as such rather than passing the spread off as the interest rate.
    struct = rt.get("structure") or {}
    sp = struct.get("spread")
    for c, lab in (("ltv", "LTV"), ("ltc", "LTC")):
        if c in can:
            cs.append(_line(lab, _pct(_val(can, c)), _src(can, c)))
    # Rate / spread: on floating debt prefer the spread the model CARRIES (a per-
    # period spread row) over the input-cell scan, which often misfires (0.00%).
    if is_floating and sp:
        cs.append(_line("Spread (over index)", _pct(sp["value"]), f"`{sp['source']}`"))
    elif "interest_rate" in can:
        cs.append(_line("Spread (over index)" if is_floating else "Interest rate",
                        _pct(_val(can, "interest_rate")), _src(can, "interest_rate")))
    if is_floating and struct.get("floor"):     # show the floor alongside the spread
        fl = struct["floor"]
        cs.append(_line("Rate floor", _pct(fl["value"]), f"`{fl['source']}`"))
    for c, lab in (("dscr", "DSCR"), ("debt_yield", "Debt yield")):
        if c in can:
            v = _val(can, c)
            cs.append(_line(lab, _x(v) if c == "dscr" else _pct(v), _src(can, c)))
    if rt.get("type") in ("floating", "fixed"):
        ev = rt.get("evidence", [])
        if is_floating:
            idx = [e for e in ev if _RE_INDEX.search(e)]
            caps = [e for e in ev if _RE_CAP.search(e)]
            bits = []
            if idx:
                bits.append("index-linked (" + "; ".join(idx[:2]) + ")")
            if caps:
                bits.append(f"{len(caps)} rate cap{'s' if len(caps) > 1 else ''} "
                            + "(" + "; ".join(caps[:2]) + ")")
            detail = " · ".join(bits) or "; ".join(ev[:2])
            cs.append(_line("Rate type", "Floating", detail, " ⚠ exposed to rate moves"))
        else:
            cs.append(_line("Rate type", "Fixed", "; ".join(ev[:2])))
    sections["capital_structure"] = "\n".join(cs)

    # --- Return Profile ---------------------------------------------------
    rp = ["#### Return Profile"]
    for c, lab in (("levered_irr", "Levered IRR"), ("unlevered_irr", "Unlevered IRR")):
        if c in can:
            rp.append(_line(lab, _pct(_val(can, c)), _src(can, c), " ✓ validated"))
    for c, lab in (("equity_multiple", "Levered equity multiple"),
                   ("unlevered_equity_multiple", "Unlevered equity multiple")):
        if c in can:
            rp.append(_line(lab, _x(_val(can, c)), _src(can, c)))
    h = dt.get("hold")
    if h and h.get("months"):
        early = (f" — _sells at month {h['months']} of a {h['model_months']}-month model_"
                 if h.get("sells_before_model_end") else "")
        rp.append(_line("Hold period", f"{h['months']} mo ({h['years']:g} yr)",
                        f"`{h.get('source','')}`", early))
    for c, lab in (("sale_price", "Sale price"), ("exit_cap", "Exit cap"),
                   ("yield_on_cost", "Yield on cost")):
        if c in can:
            v = _val(can, c)
            disp = _pct(v) if c == "exit_cap" or c == "yield_on_cost" else _money(v)
            rp.append(_line(lab, disp, _src(can, c)))
    # Going-in cap = going-in (year-1) NOI / total cost. Derive it here from the
    # reconciled roll-up: the going-in NOI must be in the same full-$ units as the
    # cost, and it must be the GOING-IN year — not stabilized. (deal_truth derives
    # it off an unreconciled NOI whose units/year can be wrong, e.g. Westview's
    # $000s NOI ÷ full-$ cost gave 0.01%.)
    gi_noi = (traj.get("noi") or {}).get("going_in")
    cost = _val(can, "total_cost") or _val(can, "purchase_price")
    if isinstance(gi_noi, (int, float)) and cost:
        rp.append(_line("Going-in cap", _pct(gi_noi / cost),
                        "`derived: going-in NOI / total cost`"))
    elif "going_in_cap" in can:
        rp.append(_line("Going-in cap", _pct(_val(can, "going_in_cap")), _src(can, "going_in_cap")))
    sections["return_profile"] = "\n".join(rp)

    # --- Cash Flow / NOI (grounded roll-up) -------------------------------
    cf = ["#### Cash Flow / NOI Trajectory"]
    noi = traj.get("noi")
    if noi:
        gi, st, ex = noi.get("going_in"), noi.get("stabilized"), noi.get("exit")
        cf.append(_line("NOI", f"{_money(gi)} going-in → {_money(st)} stabilized → {_money(ex)} exit",
                        f"`{noi['source']}`"))
        if isinstance(gi, (int, float)) and isinstance(st, (int, float)) and gi:
            cf.append(_line("NOI growth (going-in → stabilized)", _pctf(st/gi - 1)))
        # Revenue must be >= NOI (NOI = revenue - opex, opex >= 0). When the picked
        # revenue row is below NOI it is the wrong row / wrong scope (e.g. St Regis,
        # whose consolidated hotel revenue isn't captured as one row) — show neither
        # the revenue nor a margin derived from it, rather than a >100% margin.
        rev = traj.get("revenue")
        rev_st = rev.get("stabilized") if rev else None
        rev_num = isinstance(rev_st, (int, float)) and isinstance(st, (int, float)) and st > 0
        rev_ok = rev_num and rev_st >= st
        rev_below = rev_num and rev_st < st          # impossible: revenue < NOI
        if rev_ok:
            cf.append(_line("NOI margin (stabilized)", _pctf(st / rev_st)))
        for c, lab in (("revenue", "Revenue"), ("opex", "Operating expenses")):
            if c == "revenue":
                if rev_below:
                    cf.append("- _Revenue not shown — the model's revenue rows don't "
                              "reconcile to NOI (revenue reads below NOI)._")
                if not rev_ok:               # below NOI, or unparseable — skip the line
                    continue
            tr = traj.get(c)
            if tr:
                cf.append(_line(lab, f"{_money(tr.get('going_in'))} → {_money(tr.get('stabilized'))}",
                                f"`{tr['source']}`"))
    else:
        cf.append("_No operating line items found in the model's cash-flow sheets._")
    sections["cash_flow"] = "\n".join(cf)

    # --- CapEx ------------------------------------------------------------
    cp = ["#### CapEx"]
    cx = traj.get("capex")
    if cx:
        cp.append(_line("CapEx / reserves",
                        f"{_money(cx.get('going_in'))} going-in → {_money(cx.get('stabilized'))} stabilized",
                        f"`{cx['source']}`"))
    else:
        cp.append("_No CapEx / reserve line identified._")
    sections["capex"] = "\n".join(cp)

    # --- Summary cross-check (engine vs the model's headline) -------------
    sc_rows = dt.get("summary_check", [])
    if sc_rows:
        sx = ["#### Summary Cross-Check — engine vs the model's headline"]
        for r in sc_rows:
            ev = _pct(r["engine"]) if r["kind"] == "rate" else _money(r["engine"])
            sv = _pct(r["summary"]) if r["kind"] == "rate" else _money(r["summary"])
            mark = "✓" if r["match"] else "✗ **mismatch — engine wins**"
            sx.append(f"- **{r['label']}:** engine {ev} vs summary {sv} {mark} "
                      f"`{r.get('source','')}`")
        sections["summary_check"] = "\n".join(sx)

    order = ["capital_structure", "return_profile", "cash_flow", "capex", "summary_check"]
    md = "### Deal Analysis — grounded in the cash-flow model\n\n" + \
        "\n\n".join(sections[k] for k in order if k in sections)
    return {"ok": True, "md": md, "sections": sections, "dt": dt, "traj": traj}


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        r = build_analysis(a)
        print("\n" + ("=" * 80) + f"\n{Path(a).name}  ok={r['ok']}\n" + ("=" * 80))
        print(r["md"])
