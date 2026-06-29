"""Resolve Moose business context from knowledge files."""

from __future__ import annotations

from pathlib import Path
from typing import Any


MOOSE_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = MOOSE_ROOT / "knowledge"


def load_simple_yaml(path: str | Path) -> dict[str, Any]:
    """Load Moose knowledge YAML.

    PyYAML is the intended parser. The narrow fallback keeps local intake usable in an
    environment where dependencies have not been installed yet.
    """
    try:
        import yaml

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return data or {}
    except ModuleNotFoundError:
        return _load_simple_yaml_fallback(path)


def _load_simple_yaml_fallback(path: str | Path) -> dict[str, Any]:
    """Load the small YAML subset used by Moose knowledge files."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue

        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        if raw_value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(raw_value)

    return root


def _parse_scalar(value: str) -> Any:
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item.strip()) for item in inner.split(",")]
    return value


class ContextResolver:
    """Assemble business context for a document type from Moose knowledge files."""

    def __init__(self, knowledge_dir: str | Path = KNOWLEDGE_DIR) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.document_types = load_simple_yaml(self.knowledge_dir / "document_types.yaml").get(
            "document_types", {}
        )
        self.functional_work = load_simple_yaml(self.knowledge_dir / "functional_work.yaml").get(
            "functional_work", {}
        )
        self.initiatives = load_simple_yaml(self.knowledge_dir / "initiatives.yaml").get(
            "initiatives", {}
        )
        self.routing_rules = load_simple_yaml(self.knowledge_dir / "routing_rules.yaml").get(
            "routing_rules", {}
        )

    def resolve(self, document_type: str) -> dict[str, Any]:
        """Resolve lifecycle, decision, function, initiative, evidence, and pipeline context."""
        if document_type == "unknown":
            return self._unknown_context()

        document_context = self.document_types.get(document_type)
        if not document_context:
            return self._unknown_context()

        routing_rule = self.routing_rules.get(document_type, self.routing_rules.get("unknown", {}))
        related_initiatives = document_context.get("related_initiatives") or []
        initiative_context = {
            name: self.initiatives.get(name, {})
            for name in related_initiatives
        }

        return {
            "lifecycle_stage": document_context.get("lifecycle_stage"),
            "decision_layer": document_context.get("decision_layer"),
            "functional_work": document_context.get("parent_functional_work"),
            "related_initiatives": related_initiatives,
            "expected_evidence": document_context.get("expected_evidence") or [],
            "recommended_pipeline": document_context.get("recommended_pipeline")
            or routing_rule.get("pipeline"),
            "document_type_context": document_context,
            "initiative_context": initiative_context,
        }

    def _unknown_context(self) -> dict[str, Any]:
        unknown_rule = self.routing_rules.get("unknown", {})
        return {
            "lifecycle_stage": None,
            "decision_layer": None,
            "functional_work": None,
            "related_initiatives": [],
            "expected_evidence": [],
            "recommended_pipeline": unknown_rule.get("pipeline", "human_review"),
            "document_type_context": {},
            "initiative_context": {},
        }
