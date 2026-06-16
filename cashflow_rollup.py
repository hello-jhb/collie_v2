"""
cashflow_rollup.py — deterministic full read + annual roll-up of the cash-flow model.

The problem this solves: asking GPT to read NOI off a monthly cash-flow tab fails,
because the tab is rendered TRUNCATED (first ~60 columns, char-capped) and GPT
can't roll a wide time series up in its head — so it fabricates cell refs and the
trust engine omits everything.

The fix (the user's instruction): read the financial-model sheet IN ITS ENTIRETY
— every column — detect the period axis, and roll every line item up to ANNUAL
totals deterministically. The result is a compact annual table that (a) is
grounded in the real cells, (b) loses nothing to truncation, and (c) is small
enough to hand to GPT in full for narration. Crucial info lives in the first few
columns (row labels), so those are always captured.

No GPT, no per-file logic. Reuses the spine's axis detection (dates / years /
text headers, the same code that already validated across the corpus).

Public:
    rollup_sheet(grid, name)         -> annual line-item roll-up of one sheet
    rollup_model(file_path, sheets)  -> roll up the cash-flow model sheet(s)
    concept_trajectories(rollup)     -> {concept: {by_year, going_in, stabilized, exit}}
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from cashflow_spine import _load_grids, _date_run, _num, periodicity_of
from workbook_map import _concept_of

log = logging.getLogger("fb.rollup")
if not log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("[fb.rollup] %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

ROLLUP_VERSION = "2026-06-15.1"

# Line-item concepts that are FLOWS (roll up by SUM). Everything else (rates,
# ratios, balances, occupancy, ADR) is not summable and is ignored for roll-up.
_FLOW_CONCEPTS = {"noi", "revenue", "opex", "capex", "debt_service",
                  "levered_cf", "unlevered_cf"}

# Words that mark a running balance / waterfall / equity line — NOT an operating
# flow. Such a row can out-mass a real revenue/NOI line and hijack the pick.
_NON_OPERATING_WORDS = ("balance", "cumulative", "running", "waterfall",
                        "distribution", "promote", "contribution", "beginning",
                        "ending", "trap", "reserve account", "irr", "multiple")


def _is_operating_row(label: str) -> bool:
    l = (label or "").lower()
    return not any(w in l for w in _NON_OPERATING_WORDS)


def _label_col(grid: list[tuple], first_period_col: int) -> int:
    """The column before the period axis with the most text — the line-item
    labels. (A stray label in column A must not hijack a sheet whose labels are
    in B; pick the densest column.)"""
    best_c, best_n = 0, -1
    for c in range(0, max(1, first_period_col)):
        n = sum(1 for row in grid
                if c < len(row) and isinstance(row[c], str) and row[c].strip())
        if n > best_n:
            best_c, best_n = c, n
    return best_c


def rollup_sheet(grid: list[tuple], name: str) -> dict | None:
    """Read a sheet IN FULL, find its period axis, and roll every labelled line
    item up to annual totals. Horizontal axis (periods across columns) — the
    dominant cash-flow layout. Returns None if no period axis is found."""
    # Best horizontal axis = the row with the longest run of dates.
    best = None
    for r, row in enumerate(grid):
        run = _date_run(list(row))
        if run and (best is None or len(run) > len(best[1])):
            best = (r, run)
    if not best:
        return None
    arow, run = best
    cols = [i for i, _ in run]
    dates = [d for _, d in run]
    periodicity = periodicity_of([(d, 0.0) for d in dates])
    lc = _label_col(grid, cols[0])

    items: list[dict] = []
    for r in range(len(grid)):
        if r == arow:
            continue
        label = grid[r][lc] if lc < len(grid[r]) else None
        if not (isinstance(label, str) and label.strip()):
            continue
        pairs = [(dates[i], _num(grid[r][c]))
                 for i, c in enumerate(cols) if c < len(grid[r])]
        nums = [(d, v) for d, v in pairs if v is not None]
        if len(nums) < 3:
            continue
        by_year: dict[int, float] = {}
        months: dict[int, int] = {}
        for d, v in nums:
            by_year[d.year] = by_year.get(d.year, 0.0) + v
            months[d.year] = months.get(d.year, 0) + 1
        items.append({
            "label": label.strip()[:48], "row": r + 1,
            "concept": _concept_of(label),
            "by_year": dict(sorted(by_year.items())),
            "months_per_year": months,
            "total": sum(v for _, v in nums), "n_periods": len(nums),
        })
    years = sorted({y for it in items for y in it["by_year"]})
    return {"sheet": name, "axis_row": arow + 1, "periodicity": periodicity,
            "years": years, "line_items": items}


def rollup_model(file_path: str | Path, sheets: list[str] | None = None) -> dict:
    """Roll up the cash-flow model sheet(s). `sheets=None` rolls up EVERY sheet
    with a period axis (the operating proforma and the CF tab can be different
    sheets — NOI often lives on the proforma, the streams on the CF tab). Returns
    the per-sheet roll-ups plus a merged line-item list."""
    grids = _load_grids(Path(file_path))
    names = sheets if sheets is not None else list(grids.keys())
    rollups = []
    for s in names:
        if s in grids:
            ru = rollup_sheet(grids[s], s)
            if ru and ru["line_items"]:
                rollups.append(ru)

    # NB: line items are reported in each sheet's NATIVE units. A sheet can be in
    # $ and another in $000s; resolving absolute scale requires the deal anchor
    # (NOI/exit_cap ≈ sale, debt+equity=cost), which the caller (deal_truth) has —
    # cross-sheet peak-ratio guessing mis-scales unlike sheets and is avoided here.
    line_items = [it | {"sheet": ru["sheet"]} for ru in rollups for it in ru["line_items"]]
    return {"version": ROLLUP_VERSION, "sheets": [r["sheet"] for r in rollups],
            "rollups": rollups, "line_items": line_items}


def _full_year_value(item: dict, pick: str) -> float | None:
    """A headline value from a line item's annual roll-up, using only FULL years
    (a partial first/last calendar year understates a flow)."""
    by_year = item["by_year"]
    mpy = item.get("months_per_year", {})
    mx = max(mpy.values(), default=1)
    full = [(y, v) for y, v in by_year.items() if mpy.get(y, 1) >= max(1, mx - 2)]
    pos = [(y, v) for y, v in full if abs(v) > 1] or [(y, v) for y, v in by_year.items() if abs(v) > 1]
    if not pos:
        return None
    if pick == "going_in":
        return next((v for _, v in pos if v > 0), pos[0][1])
    if pick == "exit":
        return pos[-1][1]
    if pick == "stabilized":
        return max((v for _, v in pos), key=abs)
    return None


def _traj(it: dict) -> dict:
    return {
        "label": it["label"], "source": f"{it['sheet']}!row{it['row']}",
        "by_year": it["by_year"],
        "going_in": _full_year_value(it, "going_in"),
        "stabilized": _full_year_value(it, "stabilized"),
        "exit": _full_year_value(it, "exit"),
    }


def concept_trajectories(rollup: dict) -> dict[str, dict]:
    """Per FLOW concept, the single best consolidated line item (most periods,
    then largest magnitude — a total dominates its components, avoiding the
    double-count of summing component + total rows). The operating statement
    (revenue / opex / NOI / capex / debt service) is anchored to the SHEET where
    NOI was found, so the lines are mutually consistent (same context + units);
    the cash-flow streams are taken wherever they live."""
    def pick(concept, sheet=None):
        cands = [it for it in rollup["line_items"]
                 if it.get("concept") == concept and _is_operating_row(it["label"])
                 and (sheet is None or it["sheet"] == sheet)]
        return max(cands, key=lambda it: (it["n_periods"], abs(it["total"]))) if cands else None

    out: dict[str, dict] = {}
    noi = pick("noi")
    anchor = noi["sheet"] if noi else None
    if noi:
        out["noi"] = _traj(noi)
    for concept in ("revenue", "opex", "capex", "debt_service"):
        it = pick(concept, anchor) or pick(concept)   # prefer NOI's sheet
        if it:
            out[concept] = _traj(it)
    for concept in ("unlevered_cf", "levered_cf"):
        it = pick(concept)
        if it:
            out[concept] = _traj(it)
    return out


# ---------------------------------------------------------------------------
# Corpus harness — roll up each model's engine and show the NOI/rev/opex trend
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from cashflow_spine import find_spine
    args = sys.argv[1:]
    targets: list[Path] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            targets += sorted(p.glob("*.xlsx"))
        elif p.exists():
            targets.append(p)
    targets = [t for t in targets if not t.name.startswith("~$")]
    if not targets:
        print("usage: python cashflow_rollup.py <dir-or-files>")
        raise SystemExit(1)

    def fmt(v):
        if v is None:
            return "—"
        a = abs(v)
        return f"{v/1e6:.1f}M" if a >= 1e6 else f"{v/1e3:.0f}K" if a >= 1e3 else f"{v:.0f}"

    for t in targets:
        sp = find_spine(t)
        anchors = sp.diagnostics.get("anchor_sheets") or []
        print("\n" + "=" * 90)
        print(f"{t.name}   engine anchors: {anchors or '—'}")
        ru = rollup_model(t)                      # roll up EVERY period-axis sheet
        traj = concept_trajectories(ru)
        if not traj:
            print(f"  rolled up {len(ru['line_items'])} line items; no flow concept matched")
        for concept in ("revenue", "opex", "noi", "capex", "debt_service",
                        "unlevered_cf", "levered_cf"):
            tr = traj.get(concept)
            if not tr:
                continue
            print(f"  {concept:<13} {fmt(tr['going_in']):>8} → {fmt(tr['exit']):>8}  "
                  f"({fmt(tr['stabilized'])} stab)  '{tr['label'][:26]}'  {tr['source']}")
