# Moose Roadmap

## 5-Day Foundation Sprint

### Day 1: Domain Foundation

- Preserve the Moose Domain Model as the source of truth.
- Create knowledge files for functional work, initiatives, document types, and routing.
- Create initial schemas for document identity, agent results, claims, and verified facts.
- Create skeletal agents, Trust Engine modules, prompts, and pipeline orchestration.

### Day 2: File Identification and Routing

- Implement the File Identification Agent contract.
- Load and validate `knowledge/document_types.yaml` and `knowledge/routing_rules.yaml`.
- Route known document types to skeletal pipelines.
- Route ambiguous or low-confidence files to human review.
- Add tests for document identity schema validation and routing outcomes.

### Day 3: Workbook Orientation and Model Brief

- Implement workbook orientation for financial models and budget workbooks.
- Produce a model brief that describes workbook purpose, tabs, schedules, assumptions, and
  likely authoritative areas.
- Keep orientation separate from claim extraction.

### Day 4: Claim Extraction and Trust Engine Verification

- Implement claim extraction contracts for priority document types.
- Build code-based verification checks for grounding, value matching, authority, units,
  consistency, and contradictions.
- Emit verified facts only after Trust Engine evaluation.

### Day 5: Reasoning and First End-to-End Demo

- Implement the Reasoning Agent against verified facts.
- Produce a first recommendation response with citations to fact IDs.
- Demonstrate upload through recommendation for one controlled document type.
- Document open caveats and next production hardening tasks.
