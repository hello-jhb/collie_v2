# Moose Frontend Baseline Demo

This demo exercises the sprint path against `sample/BAC_vClosing.xlsx`.

## Run

```bash
streamlit run moose_app.py
```

In the sidebar, keep **Use sample/BAC_vClosing.xlsx** checked and click **Run Moose**.

## LLM Setup

Moose reads `OPENAI_API_KEY` from Streamlit secrets or the environment.

Without an API key, Moose still runs end to end using the Collie v2 fallback bridge. The frontend shows that fallback usage in the facts table, timeline, caveat card, and agent trace.

## Expected Baseline Behavior

The sample workbook should be identified as a `financial_model` and routed to `financial_model_pipeline`.

Moose should show:

- File Understanding card with type, confidence, and pipeline.
- Processing Timeline for intake, mental model, claim discovery, grounding, verification, and reasoning.
- Verified Facts table with `origin` values of `gpt_native` or `fallback`.
- Issues / Caveats card with verification status counts.
- Evidence Drawer with code verification checks for each fact.
- Agent Trace with intake, mental model, discovery comparison, grounding stats, and reasoning output.

## CLI Baseline

```bash
python3 -m moose.experiments.day5_trust_engine_demo sample/BAC_vClosing.xlsx
```

This prints extracted claims, verification summary, verified facts, caveats, reconciliation notes, GPT-vs-fallback comparison, and diagnostics.
