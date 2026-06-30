# Moose Frontend Demo

This demo exercises the upload-first Moose frontend path with an Excel workbook.

## Run

```bash
streamlit run moose_app.py
```

Upload an Excel workbook in the sidebar and click **Run Moose**.

## LLM Setup

Moose reads `OPENAI_API_KEY` from Streamlit secrets or the environment.

Without an API key, Moose still runs end to end using the Collie v2 fallback bridge. The frontend shows that fallback usage in the facts table, timeline, caveat card, and agent trace.

## Expected Behavior

Financial model workbooks should be identified as `financial_model` and routed to `financial_model_pipeline`.

Moose should show:

- File Understanding card with type, confidence, and pipeline.
- Processing Timeline for intake, mental model, claim discovery, grounding, verification, and reasoning.
- Verified Facts table with `origin` values of `gpt_native` or `fallback`.
- Issues / Caveats card with verification status counts.
- Evidence Drawer with code verification checks for each fact.
- Agent Trace with intake, mental model, discovery comparison, grounding stats, and reasoning output.

## Optional CLI Smoke Test

```bash
python3 -m moose.experiments.day5_trust_engine_demo path/to/workbook.xlsx
```

This prints extracted claims, verification summary, verified facts, caveats, reconciliation notes, GPT-vs-fallback comparison, and diagnostics.
