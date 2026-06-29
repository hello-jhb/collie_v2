# Moose Architecture

Moose is a GPT-first architecture for commercial real estate investment work. It uses
Collie code only where useful, and only after Moose's contracts make the boundary clear.

TODO(Day 2+): Treat this document as the intended architecture, not a production flow. The
current implementation is scaffold-only and does not perform GPT calls, extraction, or
frontend routing.

## Intended Flow

```
Upload
  -> File Identification Agent
  -> Pipeline Router
  -> Specialized Comprehension Agent
  -> Claim Extraction Agent
  -> Code Trust Engine
  -> Verified Facts Store
  -> Reasoning Agent
  -> Recommendation
```

## Components

### Upload

Receives a user-provided artifact and preserves its file path, name, format, and any
available metadata. Upload does not infer business meaning by itself.

### File Identification Agent

Interprets the uploaded file in the context of the Moose Domain Model. It proposes the
document type, lifecycle stage, decision layer, functional work, initiative, confidence,
evidence, and recommended pipeline.

### Pipeline Router

Routes the document identity to a specialized pipeline using `knowledge/routing_rules.yaml`.
Unknown, low-confidence, or ambiguous files route to human review.

### Specialized Comprehension Agent

Builds a document-specific understanding of structure and business context. For workbooks,
this may include orientation across tabs, sections, model purpose, and key schedules. For
other documents, this may include sections, clauses, tables, parties, dates, and obligations.

### Claim Extraction Agent

Extracts structured claims from the comprehension output. A claim is an interpretation of
evidence, not yet a fact. Every claim must cite source evidence and carry extraction
confidence and reasoning.

For financial model workbooks, the intended Moose architecture is:

```
Mental Model
  -> Workbook Evidence Pack
  -> WorkbookClaimDiscoveryAgent
  -> Code Grounding Validation
  -> Grounded Claim Set
```

The primary path is GPT claim discovery from bounded workbook evidence. The deterministic
workbook claim extractor is a temporary fallback scaffold for cases where the LLM discovery
interface is unavailable. It must not become Moose's long-term extraction architecture.

For baseline parity while GPT discovery is still stubbed, Moose may use a temporary
Collie v2 canonical-truth bridge inside the fallback extractor. That bridge exists only to
prevent regressions against known workbooks and to make Trust Engine diagnostics testable.
It is fallback-only, carries caveats for row-derived facts, and should be removed once GPT
claim discovery recovers the same claims from bounded evidence.

Day 6 adds Moose-native GPT claim discovery behind `LLMClient`. GPT receives the Mental
Model plus compact Workbook Evidence Pack snippets and candidate neighborhoods, then returns
schema-shaped claims with sheet/cell citations. Code grounding rejects unsupported GPT
claims before the Trust Engine verifies grounded claims. The Collie v2 bridge remains
available only when the LLM is unavailable or GPT-native grounded output is insufficient.

### Code Trust Engine

The Trust Engine is not a GPT agent.

The Trust Engine is code-based verification. It evaluates claims for grounding, value match,
identity, authority, consistency, unit or scale interpretation, and contradiction. It emits
verified facts, caveated facts, review needs, contradictions, or rejections.

### Verified Facts Store

Stores only Trust Engine outputs. Reasoning receives verified facts and caveated facts, not
raw claims. The first Moose foundation uses in-memory contracts only; persistence is a later
implementation decision.

### Reasoning Agent

Answers professional questions and prepares recommendations using only verified facts. It
must cite supporting fact IDs and surface caveats, risks, and open questions.

### Recommendation

Returns an action-oriented conclusion with supporting verified facts, risks, caveats,
suggested next steps, confidence, and open questions.

## Operating Rule

GPT may interpret.

Code must verify.

GPT may reason only after verification.
