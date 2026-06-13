# Collie v2 — Engine Architecture

Collie v2 is the **comprehension-first** fork (the 2026-06-12 pivot). Instead of
cell-matching a checklist and gating on a human, the engine reads the model
whole the way Claude reads Excel, then **earns trust from cross-checks** so the
human gate can be removed. Trust becomes a silent per-number confidence score,
not a mandatory confirm.

```
Upload → Orient(cached) → Read key tabs whole → Comprehend(brief+facts)
       → Trust engine → Finalize(verified only) → Persist as SSOT
       → Deep dives on demand → Report
```

See the day-by-day rationale in [DEVLOG_2026-06-10](DEVLOG_2026-06-10.md),
[DEVLOG_2026-06-11](DEVLOG_2026-06-11.md), and
[DEVLOG_2026-06-12](DEVLOG_2026-06-12.md).

---

## 1. End-to-end pipeline (hero path — LLM present)

| # | Stage | Module(s) | What it does | LLM | Output |
|---|-------|-----------|--------------|-----|--------|
| 1 | **Upload & persist** | `app.py`, `extraction_cache.py` | Save workbook to `uploads/`; always re-persist if the disk copy went missing (ephemeral-FS guard) | — | file on disk + `sha256` |
| 2 | **Orient** | `workbook_orientation.py:orient_workbook` | Deterministic, read-only. Roles every sheet (summary/inputs/returns/model/support/other) from content+structure: keyword concentration, hardcode ratio, internal-formula density, cross-sheet pull flow, time-series shape. Sheet name = weak bonus. Disk-cached (`cache/orientation/`) | none | workbook map `{sheet→role, confidence, signals}` + tier map |
| 3 | **Read key tabs whole** | `workbook_orientation.py:analyst_reading_stack` (`select_read_sheets` + `render_sheets_text`) | Pick the analyst's short stack (quota 4 summary / 2 inputs / 2 returns, name-tier tiebreak), render whole sheets as text with every A1 ref + `*` hardcode marks. Preserves table structure | none | `(sheets_read, cells_block)` |
| 4 | **Comprehend (Model Brief)** | `model_brief.py:build_model_brief` | ONE strong-model read → `{identity, facts[cell-cited], brief{overview, key_stats, debt, returns, model_structure}}`. Disk-cached by hash+version+model | 1× gpt-4o | brief dict (narrative + structured facts) |
| 5 | **Trust engine** | `trust_engine.py:score_facts` | Score every cited fact on 5 signals → verdict show/flag/omit. Replaces the human gate | 1× gpt-4o (challenge) | facts + `trust` block + summary |
| 6 | **Finalize** | `model_brief.py:finalize_brief` | Rewrite narrative from verified facts only; flagged → "(unverified)", omitted dropped. Deterministic fallback appends a note. The "no wrong data" guarantee | 1× gpt-4o | final `brief_md` |
| 7 | **Render (gate demoted)** | `app.py:_render_model_brief`, `_render_trust_panel` | Brief is the hero; 22-field checklist collapsed to an optional expander. "Run analysis →" always enabled — no mandatory human confirm | — | UI |
| 8 | **Persist brief as SSOT** | `app.py:_persist_brief_to_ssot` → `ssot.write_layer` | Verified brief facts written as the underwriting SSOT (`metrics` + `bounded_metrics`). Omitted dropped, flagged→`suspicious`, displays magnitude-normalized. No re-extraction — one fact set carries through | — | `layers.underwriting` SSOT |
| 9 | **Deep dives (on demand)** | `scenarios/deep_dives.py:focused_dive` | Pick the topic's own sheets by name-keyword, read whole, extract facts+narrative, run the same trust chain scoped to the dive's sheets, finalize, append a Fact Check | 3× gpt-4o (read → challenge → finalize) | trust-scored section |
| 10 | **Report → SSOT** | `app.py:_generate_report` | Memorialize verified facts + brief + kept findings into one report; persist as `deal_report` | 1× gpt-4o | final report md |

---

## 2. Trust engine — the 5 signals that replace the human

| Signal | Type | Check | Failure effect |
|--------|------|-------|----------------|
| **Grounded** | Deterministic | Cited cell actually holds the claimed value (×1000 / ×100 scale slack; right-value/wrong-cell recovery scans the sheet & corrects provenance) | Not grounded → **omit** (anti-fabrication floor) |
| **Authoritative** | Deterministic | Cell sits on an oriented summary/inputs/returns tab (tier ≤ 3); dives use the topic's own sheets | Lowers confidence to medium |
| **Reconciles** | Deterministic | Fact satisfies a deal identity it joins: Price×Cap≈NOI, Exit Value×Exit Cap≈Exit NOI, Debt+Equity≈Basis, LTV≈Debt/Price (normalized magnitudes, 12% tol) | Fail → **flag** (conflict) |
| **Challenged** | 1× gpt-4o | Adversarial re-read: does the cell agree, or is there a more-authoritative conflicting cell? (corroboration + challenge collapsed into one call) | Disagree → **flag**; agree can rescue an unconfirmed cell to medium |

**Verdict logic**

```
not grounded                                            → omit  (low)
grounded + (reconcile-fail | challenge-disagree)        → flag  (low, conflict)
grounded + authoritative + (reconcile-pass | ch-agree)  → show  (high)
otherwise grounded                                      → show  (medium)
```

---

## 3. Supporting & fallback modules

The legacy gated pipeline is **not deleted** — it is the no-key fallback
(deterministic gate path) and still powers the separate `perf_vs_plan`
scenario. It is simply off the deal-review-with-key critical path.

| Module | Role | When it runs |
|--------|------|--------------|
| `aam_extractor.py` | Legacy bounded 22-field/6-group extraction (Stage-1 whitelist, cell grounding, NOI-from-pricing, hardcode preference) | No-key fallback + `perf_vs_plan` |
| `formula_tracer.py` | BFS from verified AAM cells along formula precedents to reach non-AAM metrics | Legacy confirm path |
| `financial_model_parser.py` | Table-centric parse: Workbook→Sheet→classified Table→rows inheriting periodicity; authoritative time series | Confirm-time + deep-dive time series |
| `section_reader.py`, `metric_resolver*.py`, `metric_catalog.py`, `metric_fallback.py` | Catalog validation, source hierarchy, GPT pick/fallback | Legacy path |
| `ssot.py` | Verified single-source-of-truth store (layers, identity, bounded_metrics, report) | Always |
| `scenarios/_llm.py` | Lazy key-aware OpenAI client; `MODEL=gpt-4o`, `MODEL_FAST=gpt-4o-mini` | Always |
| `knowledge_store.py` | JSON knowledge layer; only `active` patterns reach prompts; human promotes, GPT never self-teaches | Prompt injection |
| `scenarios/perf_vs_plan.py` | Plan-vs-actual scenario (keeps the legacy bounded scan) | Separate workflow |

---

## 4. Models & caches

- **gpt-4o** — comprehension surfaces: brief, challenge, finalize, dives, agent loop.
- **gpt-4o-mini** — cost-sensitive bulk: sheet classifier, insight pass, section reader, pool resolver.
- **Caches** — orientation (`cache/orientation/`) and brief (`cache/briefs/`), both keyed by file-sha256 + version, so re-uploads and reruns are ~free.

---

## 5. Known trade-offs / open items (as of 2026-06-12)

- **Orientation over-labels "summary"** (~21 tabs on St Regis incl. DW-template sheets). Harmless to the brief (name-tier ordering saves the read) but the orientation panel is noisy — tighten summary/inputs thresholds.
- **Vestigial 22-field appendix** still computes on the brief path (collapsed, deterministic) though it drives nothing.
- **Dive latency** — 3 gpt-4o calls/dive; the challenge or finalize could be made conditional.
- Multi-open consolidation (large files opened several times per ingest); prompt/knowledge-injection alignment (dives/report don't see active knowledge patterns).
