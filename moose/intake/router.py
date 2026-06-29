"""Route identified files to the next Moose pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .context_resolver import KNOWLEDGE_DIR, load_simple_yaml
from .intake_result import DocumentIdentity


NEXT_AGENT_BY_PIPELINE = {
    "financial_model_pipeline": "workbook_orientation_agent",
    "budget_workbook_pipeline": "workbook_orientation_agent",
    "fund_model_pipeline": "workbook_orientation_agent",
}


class Router:
    """Return routing metadata without executing downstream pipelines."""

    def __init__(self, knowledge_dir: str | Path = KNOWLEDGE_DIR) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.routing_rules = load_simple_yaml(self.knowledge_dir / "routing_rules.yaml").get(
            "routing_rules", {}
        )

    def route(
        self,
        document_identity: DocumentIdentity | dict[str, Any],
        resolved_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Route an identified document to the next Moose pipeline metadata."""
        identity = (
            document_identity.as_dict()
            if isinstance(document_identity, DocumentIdentity)
            else document_identity
        )
        document_type = identity.get("document_type", "unknown")
        rule = self.routing_rules.get(document_type, self.routing_rules.get("unknown", {}))
        pipeline_name = resolved_context.get("recommended_pipeline") or rule.get("pipeline", "human_review")
        human_review_required = bool(
            identity.get("human_review_required") or rule.get("human_review_required", False)
        )

        if human_review_required:
            pipeline_name = "human_review"

        next_agent = NEXT_AGENT_BY_PIPELINE.get(pipeline_name, "specialized_comprehension_agent")
        if pipeline_name == "human_review":
            next_agent = "human_review"

        return {
            "pipeline_name": pipeline_name,
            "next_agent": next_agent,
            "reason": self._reason(document_type, pipeline_name, human_review_required),
            "human_review_required": human_review_required,
        }

    def _reason(self, document_type: str, pipeline_name: str, human_review_required: bool) -> str:
        if human_review_required:
            return f"Document type {document_type} requires human review before routing."
        return f"Document type {document_type} maps to {pipeline_name}."
