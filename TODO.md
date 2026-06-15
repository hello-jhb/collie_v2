# TODO — deal-reconstruction engine

## Tier 1 proforma parsing (operating trajectory)
The operating NOI/revenue/opex trajectory should come from a **labeled operating
pro forma** first (Tier 1). Today the generic table detector
(`financial_model_parser.parse_workbook_tables`) misses some operating tabs, so
`deal_truth.operating_trajectory` falls back to Tier 1b (derive from the
unlevered cash-flow stream) or Tier 2 (summary point).

- [ ] Extend table detection to catch operating pro forma tabs the generic parser
      misses — e.g. **Pro Forma MH** in `1425 4th Ave`, whose period header is at
      row 10 ("Year Ending", `2025…2034`) with merged/label cells the detector
      doesn't lock onto.
- [ ] In `_operating_tier1`, prefer a true **labeled NOI row** (incl. "Operating
      Income") read directly from the operating model; keep rejecting all-zero
      rows (cached-zero / axis-misaligned rows must not win).
- [ ] When Tier 1 succeeds, it should outrank the Tier 1b stream-derived NOI
      (which is "operating cash flow ≈ NOI net of reserves", not pure NOI).
- [ ] Add a 1425 regression once Pro Forma MH parses: NOI provenance ==
      `operating_model`, going-in ≈ model's year-1 NOI.

## Related deferred items
- [ ] Cross-check `acquisition cost` and `total cost` against the cash flow
      itself (initial outflow / cumulative construction draws), not just the
      inputs tab — promote to a CF-validated fact when they agree.
- [ ] Tighten conflict detection in `_canonical_for_concept`: component-vs-total
      (e.g. total equity vs LP/GP split) currently flags as a conflict; it should
      recognize a part-of-whole relationship rather than disclose a false conflict.
- [ ] Feed `deal_truth` canonical facts into the GPT brief (`model_brief.py`)
      directly, so the brief's *extraction* (not just Layer 3) runs off the
      validated spine.
