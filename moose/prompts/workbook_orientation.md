# Workbook Orientation Agent Prompt Placeholder

This is a future GPT prompt contract. Day 3 does not make production GPT calls.

The Workbook Orientation Agent should receive:

- Intake result
- Workbook inspection result
- Moose business context

It should return:

- workbook_type
- likely_purpose
- important_sheets
- ignored_sheets
- likely_sections
- projection_period_guess
- confidence
- human_review_required
- reasoning

Do not extract investment metrics. Do not create claims. Do not mark anything verified.
