# Moose

Moose is the GPT-first experimental successor architecture in this clone of Collie.
Collie remains the current prototype; Moose is a separate foundation for testing a new
architecture without breaking the existing app.

Moose is organized around the Domain Model in `domain_model.md`. It starts with work
context, not documents:

```
Investment Lifecycle
  -> Decision Layer
  -> Functional Work
  -> Initiative
  -> Document
  -> Evidence
  -> Claim
  -> Verified Fact
  -> Reasoning
  -> Recommendation
```

The operating principle is:

1. GPT understands files and extracts claims.
2. Code verifies those claims.
3. GPT reasons only from verified facts.

The Trust Engine is not a GPT agent. It is code-based verification that checks grounding,
value matches, source authority, consistency, units, and contradictions before any fact is
available to reasoning.

This foundation intentionally does not wire Moose into the frontend, replace the Collie
pipeline, or perform production GPT calls.

## Day 1 Scope

This is scaffolding only. Knowledge entries are reasonable v0 assumptions derived from
`domain_model.md`; they are not complete business logic.

TODO(Day 2+): Replace v0 assumptions with validated routing behavior, examples, tests, and
source-backed verification rules.
