"""
perf_vs_plan_engine.py — the perf-vs-plan ("How are we tracking?") engine: compare
the plan's NOI to actuals, definition-matched FIRST.

V1 scope (trust first, returns second): reconciliation + NOI variance only. The
returns recalc (blended IRR / EM) is a GATED placeholder — unavailable until the
actuals provide a definition-compatible cash-flow replacement (see `returns_status`).

Stage 3 (this file): the DEFINITION MATCH — confirm the plan's NOI and the
statement's NOI mean the same thing before any comparison. The detectable basis
differences are management fee, replacement reserves, and capex placement. The
statement reports its basis DEFINITIVELY (we read every leaf, so absence is real);
the model's basis is BEST-EFFORT (a label scan, so absence is just "unknown"). A
difference we can confirm is a conflict; one we can't is surfaced as a caveat —
never papered over. We never emit a clean variance off an unconfirmed match.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from actuals_statement import _RE_MGMT, _RE_RESERVE, _RE_CAPEX
from cashflow_spine import xirr, find_spine

log = logging.getLogger("fb.pvp")
if not log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("[fb.pvp] %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

PVP_VERSION = "2026-06-16.1"

# Basis dimensions whose disagreement makes two NOIs non-comparable.
_DIMS = [("includes_mgmt_fee", "a management fee"),
         ("includes_reserves", "a replacement / capital reserve")]


def plan_basis_from_rollup(rollup: dict, noi_sheet: str | None = None) -> dict[str, Any]:
    """Best-effort NOI basis for the PLAN, by scanning the model's line-item labels
    (optionally just the NOI-anchored sheet). True if a marker line is found; None if
    not found — absence in a model does NOT prove exclusion (it may be embedded), so
    we say 'unknown', not False. That asymmetry with the statement side is honest."""
    items = [it for it in rollup.get("line_items", [])
             if noi_sheet is None or it.get("sheet") == noi_sheet]
    labels = [str(it.get("label", "")).lower() for it in items]

    def found(rx) -> bool | None:
        return True if any(rx.search(l) for l in labels) else None

    return {"includes_mgmt_fee": found(_RE_MGMT),
            "includes_reserves": found(_RE_RESERVE),
            "capex_in_opex": found(_RE_CAPEX),
            "source": noi_sheet or "all model sheets", "n_lines": len(items)}


def match_definitions(plan_basis: dict, actual_basis: dict) -> dict[str, Any]:
    """Compare plan-NOI vs actual-NOI basis. Returns:
        {verdict: confirmed|unconfirmed|conflict, confirmed: bool,
         dimensions:[{dimension, plan, actual, status}], caveats:[...]}
    `actual` is definite (True/False); `plan` is True or None (unknown)."""
    dims: list[dict] = []
    caveats: list[str] = []
    conflicts = unconfirmed = 0

    for key, phrase in _DIMS:
        plan = plan_basis.get(key)        # True | None
        act = actual_basis.get(key)       # True | False
        if act is True and plan is True:
            status = "match"
        elif act is False and plan is True:
            status, conflicts = "conflict", conflicts + 1
            caveats.append(f"Plan deducts {phrase} above NOI but the statement does not — "
                           f"the two NOIs are not like-for-like on this line.")
        elif act is True and plan is None:
            status, unconfirmed = "unconfirmed", unconfirmed + 1
            caveats.append(f"The statement deducts {phrase} above NOI; the model's treatment "
                           f"could not be confirmed — the comparison assumes it matches.")
        else:                              # act False & plan None — neither detected
            status = "assumed_consistent"
        dims.append({"dimension": key, "plan": plan, "actual": act, "status": status})

    # The statement should strike NOI BEFORE capex. If capex sits in opex (above NOI),
    # its NOI is struck after capex — non-standard and almost certainly not the plan's.
    if actual_basis.get("capex_in_opex"):
        conflicts += 1
        caveats.append("The statement strikes NOI AFTER capex (capex is above the NOI line) — "
                       "non-standard; the plan's NOI is almost certainly before capex.")

    confirmed = conflicts == 0 and unconfirmed == 0
    verdict = "confirmed" if confirmed else ("conflict" if conflicts else "unconfirmed")
    return {"version": PVP_VERSION, "verdict": verdict, "confirmed": confirmed,
            "conflicts": conflicts, "unconfirmed": unconfirmed,
            "dimensions": dims, "caveats": caveats}


def render_definition_match(m: dict) -> str:
    icon = {"confirmed": "✓", "unconfirmed": "⚠", "conflict": "✗"}[m["verdict"]]
    L = [f"{icon} NOI definition match: {m['verdict'].upper()}"]
    for d in m["dimensions"]:
        pa = {True: "yes", False: "no", None: "unknown"}
        L.append(f"   • {d['dimension']}: plan={pa[d['plan']]}, actual={pa[d['actual']]} "
                 f"→ {d['status']}")
    for c in m["caveats"]:
        L.append(f"   ⚠ {c}")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Stage 5 (Output A) — NOI variance, calendar-aligned, trust-gated
# ---------------------------------------------------------------------------

def _monthly_map(by_period: list) -> dict[str, float]:
    """[(iso_date, value), …] → {YYYY-MM: Σ value} (collapse to calendar month)."""
    out: dict[str, float] = {}
    for iso, v in by_period:
        out[iso[:7]] = out.get(iso[:7], 0.0) + v
    return out


def _reconcile_scale(plan_map: dict, actual_map: dict) -> tuple[dict, str | None]:
    """Bring the plan onto the statement's dollar scale if the model is in $000s
    and the statement in full $ (or vice versa). Power-of-1000 only — anything else
    is left alone (a real performance gap, not a units gap)."""
    import statistics
    pv = [abs(v) for v in plan_map.values() if v]
    av = [abs(v) for v in actual_map.values() if v]
    if not pv or not av:
        return plan_map, None
    ratio = statistics.median(pv) / statistics.median(av)
    if ratio >= 300:
        f = 1e3 if ratio < 3e5 else 1e6
        return {k: v / f for k, v in plan_map.items()}, f"Plan scaled ÷{f:g} to match the statement's units."
    if ratio <= 1 / 300:
        f = 1e3 if ratio > 1 / 3e5 else 1e6
        return {k: v * f for k, v in plan_map.items()}, f"Plan scaled ×{f:g} to match the statement's units."
    return plan_map, None


def _actual_to_model_scale(model_noi: dict, actual_noi: dict, overlap: set) -> float:
    """Factor to bring actual NOI onto the MODEL's units (the stream's scale) before
    splicing — power-of-1000 only, else 1.0 (a real gap, not a units gap)."""
    import statistics
    mv = [abs(model_noi[m]) for m in overlap if model_noi.get(m)]
    av = [abs(actual_noi[m]) for m in overlap if actual_noi.get(m)]
    if not mv or not av:
        return 1.0
    ratio = statistics.median(mv) / statistics.median(av)
    if ratio >= 300:
        return 1e3 if ratio < 3e5 else 1e6
    if ratio <= 1 / 300:
        return 1 / 1e3 if ratio > 1 / 3e5 else 1 / 1e6
    return 1.0


def align_noi(plan_map: dict, actual_map: dict) -> dict[str, Any]:
    """Line plan NOI against actual NOI. Prefer CALENDAR overlap (the honest
    apples-to-apples window); fall back to elapsed-index only if the two never share
    a calendar month, with the assumption made explicit."""
    overlap = sorted(set(plan_map) & set(actual_map))
    if overlap:
        basis = "calendar"
        periods = [{"period": ym, "plan": plan_map[ym], "actual": actual_map[ym],
                    "delta": actual_map[ym] - plan_map[ym]} for ym in overlap]
    else:
        basis = "elapsed"
        pk, ak = sorted(plan_map), sorted(actual_map)
        n = min(len(pk), len(ak))
        periods = [{"period": f"{ak[i]}↔plan m{i + 1}", "plan": plan_map[pk[i]],
                    "actual": actual_map[ak[i]], "delta": actual_map[ak[i]] - plan_map[pk[i]]}
                   for i in range(n)]
    pt = sum(p["plan"] for p in periods)
    at = sum(p["actual"] for p in periods)
    return {"basis": basis, "n": len(periods), "periods": periods,
            "plan_total": pt, "actual_total": at, "delta": at - pt,
            "pct": (at - pt) / abs(pt) if pt else None}


def _blend_leg(flows: list, noi_delta: dict, overlap: set) -> dict[str, Any]:
    """Blended stream = projected stream with the actual-NOI DELTA applied to the
    operating months in the overlap. We know only actual NOI (not actual capex or
    financing), so we hold those at plan and flow the NOI variance through:
        blended_CF(m) = projected_CF(m) + (actual_NOI(m) − plan_NOI(m)).
    This is correct for BOTH legs (the delta is the NOI line; capex & debt service
    sit below it, unchanged) and preserves the model's lumpy capex/TI-LC outflows."""
    blended, n = [], 0
    for i, (d, v) in enumerate(flows):
        ym = d.isoformat()[:7]
        if 0 < i < len(flows) - 1 and ym in overlap and ym in noi_delta:
            blended.append((d, v + noi_delta[ym]))
            n += 1
        else:
            blended.append((d, v))
    irr = xirr(blended)
    infl = sum(v for _, v in blended if v > 0)
    outf = sum(v for _, v in blended if v < 0)
    return {"blended_irr": irr, "blended_em": (infl / abs(outf)) if outf else None,
            "n_spliced": n}


def compute_returns(spine, model_noi: dict, actual_noi: dict, overlap: set,
                    scale: float) -> list[dict]:
    """Blended IRR/EM per leg from the actual-NOI delta (capex & financing held at
    plan). Actuals are scaled to the model's units first. The result inherits the
    NOI-variance definition match — if that's unconfirmed, so is this."""
    delta = {ym: actual_noi[ym] * scale - model_noi[ym]
             for ym in overlap if ym in actual_noi and ym in model_noi}
    out: list[dict] = []
    for leg in ("levered", "unlevered"):
        m = spine.matched.get(leg)
        if not m:
            continue
        bl = _blend_leg(m["flows"], delta, overlap)
        out.append({"leg": leg, "available": bl["blended_irr"] is not None,
                    "projected_irr": m["recomputed_irr"], "blended_irr": bl["blended_irr"],
                    "projected_em": m.get("recomputed_em"), "blended_em": bl["blended_em"],
                    "n_spliced": bl["n_spliced"],
                    "basis": "actual NOI; capex & financing held at plan"})
    return out


def build_perf_vs_plan(model_path, statement_paths, sheet: str | None = None) -> dict[str, Any]:
    """End-to-end V1: reconcile the actuals, definition-match them to the plan, and
    report the NOI variance — gating the comparison on the statement footing, and
    gating returns entirely (V1)."""
    from actuals_statement import extract_actuals, extract_actuals_files
    from cashflow_rollup import rollup_model, concept_trajectories

    paths = [statement_paths] if isinstance(statement_paths, (str, Path)) else list(statement_paths)
    a = (extract_actuals_files(paths) if len(paths) > 1
         else extract_actuals(paths[0], sheet=sheet))
    if not a.get("ok"):
        return {"ok": False, "blocked": "actuals_unreadable", "reason": a.get("reason"),
                "actuals": a}
    if not a.get("trusted"):                       # DoD #2 — do not silently compare
        return {"ok": False, "blocked": "actuals_not_trusted",
                "reason": "the statement did not foot to NOI — variance withheld until it does",
                "validation": a.get("validation"), "actuals": a}

    ru = rollup_model(model_path)
    noi_tr = concept_trajectories(ru).get("noi")
    if not noi_tr or not noi_tr.get("by_period"):
        return {"ok": False, "blocked": "plan_noi_missing",
                "reason": "could not read a projected NOI series from the model"}

    model_noi = _monthly_map(noi_tr["by_period"])             # model-native scale
    actual_map = {m["period"]: m["noi"] for m in a["months"]}
    plan_map, scale_note = _reconcile_scale(dict(model_noi), actual_map)   # for the variance display

    dm = match_definitions(plan_basis_from_rollup(ru, None), a.get("basis", {}))
    var = align_noi(plan_map, actual_map)

    # Output B — blended returns, per leg, where the actuals are definition-
    # compatible with the leg's cash flow. Needs a calendar overlap + the validated
    # streams; the levered leg stays withheld unless the statement carries the
    # financing line (debt service).
    returns: list[dict] = []
    if var["basis"] == "calendar":
        sp = find_spine(model_path)
        if sp.ok:
            overlap = {p["period"] for p in var["periods"]}
            scale = _actual_to_model_scale(model_noi, actual_map, overlap)
            returns = compute_returns(sp, model_noi, actual_map, overlap, scale)

    result = {
        "ok": True, "version": PVP_VERSION,
        "model": Path(model_path).name, "statement": a.get("file") or a.get("files"),
        "variance": var, "definition_match": dm, "returns": returns,
        "plan_noi_line": noi_tr["label"], "plan_noi_source": noi_tr["source"],
        "validation": a["validation"], "scale_note": scale_note,
        "drivers": a.get("expense_drivers", [])[:5],
    }
    result["md"] = render_perf_vs_plan(result)
    log.info("PVP %s vs %s — align=%s n=%d, var=%+.0f (%.1f%%), defmatch=%s, returns=%s",
             result["model"], a.get("file"), var["basis"], var["n"], var["delta"],
             (var["pct"] or 0) * 100, dm["verdict"],
             ",".join(f"{r['leg']}:{'✓' if r.get('available') else '—'}" for r in returns) or "none")
    return result


def render_perf_vs_plan(r: dict) -> str:
    v, dm = r["variance"], r["definition_match"]
    money = lambda x: f"${x:,.0f}"                                          # noqa: E731
    L = ["## How are we tracking? — plan vs actual", ""]

    # Reconciliation — visible, not buried (the differentiator).
    L.append("### Reconciliation")
    val = r["validation"]
    L.append(f"- **Statement self-check:** {val['n_passed']}/{val['n_checks']} identities passed "
             f"(revenue − opex = NOI, per month) ✓")
    icon = {"confirmed": "✓", "unconfirmed": "⚠", "conflict": "✗"}[dm["verdict"]]
    L.append(f"- **NOI definition match:** {icon} {dm['verdict'].upper()}")
    for c in dm["caveats"]:
        L.append(f"  - ⚠ {c}")
    L.append(f"- **Period alignment:** {v['basis']} — {v['n']} overlapping month(s)")
    if r.get("scale_note"):
        L.append(f"  - {r['scale_note']}")
    L.append("")

    # A. NOI variance.
    L.append(f"### A. NOI variance — {v['n']} elapsed month(s)")
    if v["pct"] is None:
        L.append("- _No overlapping plan period to compare._")
    else:
        track = "above" if v["delta"] >= 0 else "below"
        L.append(f"- Plan {money(v['plan_total'])}  ·  Actual {money(v['actual_total'])}  ·  "
                 f"**Δ {money(v['delta'])} ({v['pct'] * 100:+.1f}%)** — tracking {track} plan")
        L.append(f"- Plan NOI line: _{r['plan_noi_line']}_ (`{r['plan_noi_source']}`)")
        worst = sorted(v["periods"], key=lambda p: p["delta"])[:3]
        if any(p["delta"] < 0 for p in worst):
            L.append("- Biggest monthly shortfalls: "
                     + ", ".join(f"{p['period']} {money(p['delta'])}"
                                 for p in worst if p["delta"] < 0))
    L.append("")

    # B. Updated returns — actual NOI flowed through the plan's cash flows.
    L.append("### B. Updated returns (blended: actual NOI to date + plan thereafter)")
    returns = r.get("returns") or []
    if not returns:
        L.append("> ⚠ **Withheld.** No calendar-overlapping projected stream to apply "
                 "the actual NOI to.")
    for rr in returns:
        leg = rr["leg"].capitalize()
        if rr.get("available"):
            pi, bi = rr["projected_irr"], rr.get("blended_irr")
            pe, be = rr.get("projected_em"), rr.get("blended_em")
            irr_s = f"underwritten {pi * 100:.2f}% → **tracking {bi * 100:.2f}%**"
            em_s = f"; EM {pe:.2f}× → {be:.2f}×" if (pe and be) else ""
            L.append(f"- **{leg}:** {irr_s}{em_s}")
        else:
            L.append(f"- **{leg}:** ⚠ withheld — {rr.get('reason', '')}")
    if returns:
        L.append(f"- _First {returns[0]['n_spliced']} mo use actual NOI; capex & financing "
                 f"held at plan (the statement reports NOI only)._")
        if dm["verdict"] != "confirmed":
            L.append(f"- ⚠ _Subject to the NOI definition match above "
                     f"({dm['verdict']}) — same basis caveat applies to these figures._")
    return "\n".join(L)


if __name__ == "__main__":
    # usage: python perf_vs_plan_engine.py <model.xlsx> <statement.xlsx> [statement2 …]
    res = build_perf_vs_plan(sys.argv[1], sys.argv[2:])
    print(res["md"] if res.get("ok") else f"BLOCKED ({res.get('blocked')}): {res.get('reason')}")
