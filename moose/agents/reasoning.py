"""Reasoning from verified facts only."""

from __future__ import annotations

from typing import Any

from moose.llm import LLMClient, LLMUnavailable


class ReasoningAgent:
    """Reason only from verified or caveated facts."""

    allowed_statuses = {"verified", "verified_with_caveat"}

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def reason(
        self,
        question: str,
        verified_facts: list[dict[str, Any]],
        reconciliation_notes: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a professional readout grounded only in verified facts."""
        usable_facts = [
            fact for fact in verified_facts
            if fact.get("verification_status") in self.allowed_statuses
        ]
        if len(usable_facts) != len(verified_facts):
            raise ValueError("Reasoning received unverified facts.")

        try:
            return self._llm_reason(question, usable_facts, reconciliation_notes or [], context or {})
        except LLMUnavailable as exc:
            fallback = self._deterministic_reason(question, usable_facts, reconciliation_notes or [], context or {})
            fallback["reasoning_mode"] = "verified_facts_only_deterministic_fallback"
            fallback["llm_error"] = str(exc)
            fallback["caveats"] = list(dict.fromkeys(
                fallback.get("caveats", []) + ["LLM reasoning was unavailable; Moose used a deterministic fallback read."]
            ))
            return fallback

    def _deterministic_reason(
        self,
        question: str,
        usable_facts: list[dict[str, Any]],
        reconciliation_notes: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        fact_map = {
            fact.get("metric_or_subject"): fact
            for fact in usable_facts
        }
        observations = self._observations(fact_map)
        caveats = self._caveats(usable_facts, reconciliation_notes)
        open_questions = self._open_questions(fact_map, reconciliation_notes)

        return {
            "question": question,
            "reasoning_mode": "verified_facts_only_v0",
            "answer_summary": self._summary(fact_map, observations, caveats),
            "sections": self._fallback_sections(fact_map, open_questions),
            "observations": observations,
            "supporting_fact_ids": self._supporting_fact_ids(observations),
            "reconciliation_notes": reconciliation_notes,
            "caveats": caveats,
            "suggested_next_steps": self._next_steps(open_questions, caveats),
            "open_questions": open_questions,
            "confidence": self._confidence(usable_facts, caveats, open_questions),
            "context": context,
        }

    def _llm_reason(
        self,
        question: str,
        usable_facts: list[dict[str, Any]],
        reconciliation_notes: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        schema = {
            "type": "object",
            "required": [
                "answer_summary",
                "sections",
                "supporting_fact_ids",
                "caveats",
                "open_questions",
                "suggested_next_steps",
                "confidence",
            ],
            "additionalProperties": False,
            "properties": {
                "answer_summary": {"type": "string"},
                "sections": {
                    "type": "object",
                    "required": [
                        "Deal Snapshot",
                        "Capital Structure",
                        "Return Profile",
                        "Operating / NOI Read",
                        "Exit Assumptions",
                        "Debt / Refi Risk",
                        "Items Requiring Review",
                    ],
                    "additionalProperties": False,
                    "properties": {
                        "Deal Snapshot": {"type": "string"},
                        "Capital Structure": {"type": "string"},
                        "Return Profile": {"type": "string"},
                        "Operating / NOI Read": {"type": "string"},
                        "Exit Assumptions": {"type": "string"},
                        "Debt / Refi Risk": {"type": "string"},
                        "Items Requiring Review": {"type": "string"},
                    },
                },
                "supporting_fact_ids": {"type": "array", "items": {"type": "string"}},
                "caveats": {"type": "array", "items": {"type": "string"}},
                "open_questions": {"type": "array", "items": {"type": "string"}},
                "suggested_next_steps": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        }
        response = self.llm_client.complete_json(
            system_prompt=(
                "You are the Moose Investment Reasoning Agent. Reason only from the "
                "provided verified or caveated facts. Cite fact ids implicitly by listing "
                "supporting_fact_ids. Do not add market claims, recommendations, or facts "
                "that are not in the payload."
            ),
            user_payload={
                "question": question,
                "verified_or_caveated_facts": usable_facts,
                "reconciliation_notes": reconciliation_notes,
                "context": context,
                "required_sections": [
                    "Deal Snapshot",
                    "Capital Structure",
                    "Return Profile",
                    "Operating / NOI Read",
                    "Exit Assumptions",
                    "Debt / Refi Risk",
                    "Items Requiring Review",
                ],
            },
            schema=schema,
        )
        response["question"] = question
        response["reasoning_mode"] = "verified_facts_only_llm"
        response["observations"] = self._observations({
            fact.get("metric_or_subject"): fact
            for fact in usable_facts
        })
        response["reconciliation_notes"] = reconciliation_notes
        response["context"] = context
        return response

    def _observations(self, facts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        self._add_fact_observation(
            observations,
            facts,
            "investment_basis",
            "total_project_cost",
            "Total project cost is available as the current basis anchor.",
        )
        self._add_fact_observation(
            observations,
            facts,
            "capital_structure",
            "debt_amount",
            "Debt amount is available for capital structure analysis.",
        )
        self._add_fact_observation(
            observations,
            facts,
            "capital_structure",
            "equity_required",
            "Equity required is available for capital structure analysis.",
        )
        self._add_fact_observation(
            observations,
            facts,
            "debt",
            "loan_to_value",
            "Loan-to-value is available as a leverage indicator.",
        )
        self._add_fact_observation(
            observations,
            facts,
            "returns",
            "levered_irr",
            "Levered IRR is available as a return indicator.",
        )
        self._add_fact_observation(
            observations,
            facts,
            "returns",
            "equity_multiple",
            "Equity multiple is available as a return indicator.",
        )
        self._add_fact_observation(
            observations,
            facts,
            "exit",
            "sale_value",
            "Sale value is available as an exit value indicator.",
        )
        return observations

    def _add_fact_observation(
        self,
        observations: list[dict[str, Any]],
        facts: dict[str, dict[str, Any]],
        topic: str,
        metric: str,
        statement: str,
    ) -> None:
        fact = facts.get(metric)
        if not fact:
            return
        observations.append({
            "topic": topic,
            "statement": statement,
            "metric_or_subject": metric,
            "value": fact.get("verified_value"),
            "unit": fact.get("unit"),
            "source": fact.get("source"),
            "fact_id": fact.get("fact_id"),
        })

    def _summary(
        self,
        facts: dict[str, dict[str, Any]],
        observations: list[dict[str, Any]],
        caveats: list[str],
    ) -> str:
        if not observations:
            return "Moose has no verified facts available for reasoning yet."
        basis = facts.get("total_project_cost", {}).get("verified_value")
        debt = facts.get("debt_amount", {}).get("verified_value")
        levered_irr = facts.get("levered_irr", {}).get("verified_value")
        pieces = ["Moose can provide a preliminary readout from verified facts only."]
        if basis is not None and debt is not None:
            pieces.append(f"Verified basis is {basis} and verified debt is {debt}.")
        if levered_irr is not None:
            pieces.append(f"Verified levered IRR is {levered_irr}.")
        if caveats:
            pieces.append("Some caveats remain and should be resolved before final recommendation.")
        return " ".join(pieces)

    def _fallback_sections(
        self,
        facts: dict[str, dict[str, Any]],
        open_questions: list[str],
    ) -> dict[str, str]:
        def sentence(metric: str, label: str) -> str:
            fact = facts.get(metric)
            if not fact:
                return f"No verified fact is available for {label}."
            return f"{label}: {fact.get('verified_value')} {fact.get('unit') or ''} from {fact.get('source')}."

        return {
            "Deal Snapshot": sentence("total_project_cost", "Total project cost"),
            "Capital Structure": " ".join([
                sentence("debt_amount", "Debt"),
                sentence("equity_required", "Equity"),
                sentence("loan_to_value", "LTV"),
            ]),
            "Return Profile": " ".join([
                sentence("levered_irr", "Levered IRR"),
                sentence("unlevered_irr", "Unlevered IRR"),
                sentence("equity_multiple", "Equity multiple"),
            ]),
            "Operating / NOI Read": sentence("stabilized_noi", "Stabilized NOI"),
            "Exit Assumptions": " ".join([
                sentence("exit_cap_rate", "Exit cap rate"),
                sentence("sale_value", "Sale value"),
            ]),
            "Debt / Refi Risk": sentence("interest_rate", "Interest rate"),
            "Items Requiring Review": " ".join(open_questions) if open_questions else "No open questions generated from the verified fact set.",
        }

    def _supporting_fact_ids(self, observations: list[dict[str, Any]]) -> list[str]:
        return [
            str(observation["fact_id"])
            for observation in observations
            if observation.get("fact_id")
        ]

    def _caveats(
        self,
        facts: list[dict[str, Any]],
        reconciliation_notes: list[dict[str, Any]],
    ) -> list[str]:
        caveats: list[str] = []
        for fact in facts:
            caveats.extend(fact.get("caveats", []))
            if fact.get("verification_status") == "verified_with_caveat":
                caveats.append(f"{fact.get('metric_or_subject')} is verified with caveat.")
        for note in reconciliation_notes:
            if note.get("status") == "caveat" and note.get("caveat"):
                caveats.append(str(note["caveat"]))
            if note.get("status") == "not_run" and note.get("caveat"):
                caveats.append(str(note["caveat"]))
        return list(dict.fromkeys(caveats))

    def _open_questions(
        self,
        facts: dict[str, dict[str, Any]],
        reconciliation_notes: list[dict[str, Any]],
    ) -> list[str]:
        required = [
            "purchase_price",
            "total_project_cost",
            "debt_amount",
            "equity_required",
            "levered_irr",
            "equity_multiple",
            "stabilized_noi",
            "exit_cap_rate",
            "sale_value",
        ]
        questions = [
            f"Missing verified fact for {metric}."
            for metric in required
            if metric not in facts
        ]
        questions.extend(
            f"Resolve reconciliation check: {note.get('name')}."
            for note in reconciliation_notes
            if note.get("status") in {"caveat", "not_run"}
        )
        return questions

    def _next_steps(self, open_questions: list[str], caveats: list[str]) -> list[str]:
        steps = ["Review supporting fact citations before using this readout."]
        if open_questions:
            steps.append("Resolve open questions by extracting or verifying missing facts.")
        if caveats:
            steps.append("Review caveated facts and reconciliation notes.")
        steps.append("Proceed to recommendation only after reasoning requirements are satisfied.")
        return steps

    def _confidence(
        self,
        facts: list[dict[str, Any]],
        caveats: list[str],
        open_questions: list[str],
    ) -> float:
        if not facts:
            return 0.0
        base = min(0.9, 0.45 + len(facts) * 0.03)
        penalty = min(0.4, len(caveats) * 0.03 + len(open_questions) * 0.04)
        return round(max(0.1, base - penalty), 2)
