# Workbook Mental Model Prompt Placeholder

This is a future GPT prompt contract. Day 4 does not make production GPT calls.

Create a structured mental model of a financial model workbook using:

- Intake result
- Workbook inspection
- Workbook orientation
- Model brief
- Moose Domain Model context

The mental model should describe:

- document type
- workbook type
- business purpose
- decision supported
- lifecycle stage
- decision layer
- functional work
- initiative
- important sheets
- ignored sheets
- expected sections
- expected metric families
- extraction priorities
- likely authoritative sources
- caveats
- confidence

Key rule: do not extract specific metric values. Describe workbook purpose, decision
context, sections, expected metric families, and extraction priorities only.

The next step after the mental model is GPT claim discovery from a bounded Workbook
Evidence Pack. The deterministic extractor is a temporary fallback only.
