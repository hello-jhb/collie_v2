"""Simple reconciliation checks for verified facts."""

from __future__ import annotations

from typing import Any


class ReconciliationEngine:
    """Compare related facts for simple financial identity caveats."""

    def reconcile(self, verified_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return reconciliation annotations for verified facts."""
        facts = {
            fact.get("metric_or_subject"): fact
            for fact in verified_facts
            if fact.get("verification_status") in {"verified", "verified_with_caveat"}
        }
        notes: list[dict[str, Any]] = []

        self._check_sum_identity(
            notes,
            facts,
            "debt_plus_equity_equals_total_project_cost",
            "debt_amount",
            "equity_required",
            "total_project_cost",
        )
        self._check_ratio_identity(
            notes,
            facts,
            "debt_div_total_project_cost_equals_ltv",
            "debt_amount",
            "total_project_cost",
            "loan_to_value",
        )
        self._check_sale_value_identity(notes, facts)
        return notes

    def _check_sum_identity(
        self,
        notes: list[dict[str, Any]],
        facts: dict[str, dict[str, Any]],
        name: str,
        left_metric: str,
        right_metric: str,
        total_metric: str,
    ) -> None:
        required = [left_metric, right_metric, total_metric]
        if not all(metric in facts for metric in required):
            notes.append({"name": name, "status": "not_run", "caveat": f"Missing one of {required}."})
            return
        left = float(facts[left_metric]["verified_value"])
        right = float(facts[right_metric]["verified_value"])
        total = float(facts[total_metric]["verified_value"])
        variance = abs((left + right) - total)
        tolerance = max(abs(total) * 0.02, 1.0)
        status = "passed" if variance <= tolerance else "caveat"
        notes.append({
            "name": name,
            "status": status,
            "expected": total,
            "actual": left + right,
            "variance": variance,
            "caveat": None if status == "passed" else "Debt plus equity does not approximate total project cost.",
        })

    def _check_ratio_identity(
        self,
        notes: list[dict[str, Any]],
        facts: dict[str, dict[str, Any]],
        name: str,
        numerator_metric: str,
        denominator_metric: str,
        ratio_metric: str,
    ) -> None:
        required = [numerator_metric, denominator_metric, ratio_metric]
        if not all(metric in facts for metric in required):
            notes.append({"name": name, "status": "not_run", "caveat": f"Missing one of {required}."})
            return
        denominator = float(facts[denominator_metric]["verified_value"])
        if denominator == 0:
            notes.append({"name": name, "status": "not_run", "caveat": "Denominator is zero."})
            return
        actual_ratio = float(facts[numerator_metric]["verified_value"]) / denominator
        claimed_ratio = float(facts[ratio_metric]["verified_value"])
        variance = abs(actual_ratio - claimed_ratio)
        status = "passed" if variance <= 0.03 else "caveat"
        notes.append({
            "name": name,
            "status": status,
            "expected": claimed_ratio,
            "actual": actual_ratio,
            "variance": variance,
            "caveat": None if status == "passed" else "Debt divided by cost does not approximate LTV.",
        })

    def _check_sale_value_identity(
        self,
        notes: list[dict[str, Any]],
        facts: dict[str, dict[str, Any]],
    ) -> None:
        required = ["sale_value", "stabilized_noi", "exit_cap_rate"]
        if not all(metric in facts for metric in required):
            notes.append({
                "name": "sale_value_equals_noi_div_exit_cap_rate",
                "status": "not_run",
                "caveat": f"Missing one of {required}.",
            })
            return
        exit_cap = float(facts["exit_cap_rate"]["verified_value"])
        if exit_cap == 0:
            notes.append({
                "name": "sale_value_equals_noi_div_exit_cap_rate",
                "status": "not_run",
                "caveat": "Exit cap rate is zero.",
            })
            return
        actual_sale_value = float(facts["stabilized_noi"]["verified_value"]) / exit_cap
        claimed_sale_value = float(facts["sale_value"]["verified_value"])
        variance = abs(actual_sale_value - claimed_sale_value)
        tolerance = max(abs(claimed_sale_value) * 0.05, 1.0)
        status = "passed" if variance <= tolerance else "caveat"
        notes.append({
            "name": "sale_value_equals_noi_div_exit_cap_rate",
            "status": status,
            "expected": claimed_sale_value,
            "actual": actual_sale_value,
            "variance": variance,
            "caveat": None if status == "passed" else "Sale value does not approximate NOI divided by exit cap rate.",
        })
