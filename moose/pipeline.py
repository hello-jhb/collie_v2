"""Moose orchestration skeleton.

This module shows the intended flow without wiring Moose into the existing Collie app.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from moose.agents import (
    ClaimExtractor,
    FileIdentifier,
    ModelBriefAgent,
    ReasoningAgent,
    WorkbookOrientationAgent,
)
from moose.intake import (
    ContextResolver,
    FileIdentifier as IntakeFileIdentifier,
    IntakeResult,
    Router,
)
from moose.trust import ReconciliationEngine, TrustVerifier, VerificationRunResult
from moose.workbook import (
    FallbackWorkbookClaimExtractor,
    ModelBriefBuilder,
    WorkbookClaimExtractionResult,
    WorkbookClaimDiscoveryAgent,
    WorkbookClaimDiscoveryUnavailable,
    WorkbookComprehensionResult,
    WorkbookEvidencePackBuilder,
    WorkbookClaimGroundingValidator,
    WorkbookInspector,
    WorkbookMentalModelBuilder,
    WorkbookOrientationBuilder,
)


def run_intake(file_path: str | Path) -> IntakeResult:
    """Run the Day 2 Moose Intake Layer without executing downstream pipelines."""
    identifier = IntakeFileIdentifier()
    resolver = ContextResolver()
    router = Router()

    document_identity = identifier.identify(file_path)
    resolved_context = resolver.resolve(document_identity.document_type)
    route = router.route(document_identity, resolved_context)

    return IntakeResult(
        file_path=str(file_path),
        document_identity=document_identity.as_dict(),
        resolved_context=resolved_context,
        route=route,
    )


def run_financial_model_comprehension(file_path: str | Path) -> WorkbookComprehensionResult:
    """Run Day 3 workbook comprehension for a financial model workbook.

    This stops at model brief generation. It does not extract claims or run verification.
    """
    intake = run_intake(file_path)
    route = intake.route.get("pipeline_name")
    if route != "financial_model_pipeline":
        raise ValueError(f"Expected financial_model_pipeline, got {route}.")

    inspector = WorkbookInspector()
    orientation_builder = WorkbookOrientationBuilder()
    brief_builder = ModelBriefBuilder()

    inspection = inspector.inspect(file_path)
    orientation = orientation_builder.orient(intake, inspection)
    model_brief = brief_builder.build(intake, orientation)

    return WorkbookComprehensionResult(
        intake_result=intake.as_dict(),
        workbook_inspection=inspection.as_dict(),
        workbook_orientation=orientation.as_dict(),
        model_brief=model_brief.as_dict(),
    )


def run_financial_model_claim_extraction(file_path: str | Path) -> WorkbookClaimExtractionResult:
    """Run Day 4 financial model mental-model creation and claim extraction.

    This returns unverified claims. It does not run the Trust Engine or produce an
    investment recommendation.
    """
    intake = run_intake(file_path)
    route = intake.route.get("pipeline_name")
    if route != "financial_model_pipeline":
        raise ValueError(f"Expected financial_model_pipeline, got {route}.")

    inspector = WorkbookInspector()
    orientation_builder = WorkbookOrientationBuilder()
    brief_builder = ModelBriefBuilder()
    mental_model_builder = WorkbookMentalModelBuilder()
    evidence_pack_builder = WorkbookEvidencePackBuilder()
    discovery_agent = WorkbookClaimDiscoveryAgent()
    grounding_validator = WorkbookClaimGroundingValidator()
    fallback_extractor = FallbackWorkbookClaimExtractor()

    inspection = inspector.inspect(file_path)
    orientation = orientation_builder.orient(intake, inspection)
    model_brief = brief_builder.build(intake, orientation)
    mental_model = mental_model_builder.build(intake, inspection, orientation, model_brief)
    evidence_pack = evidence_pack_builder.build(file_path, mental_model)

    extraction_mode = "gpt_claim_discovery"
    claims: list[dict[str, Any]] = []
    rejected_claims: list[dict[str, Any]] = []
    discovered_claims: list[dict[str, Any]] = []
    gpt_grounded_claims: list[dict[str, Any]] = []
    gpt_rejected_claims: list[dict[str, Any]] = []
    discovery_error: str | None = None

    fallback_claims = fallback_extractor.extract(
        file_path=file_path,
        intake_result=intake,
        inspection=inspection,
        orientation=orientation,
        model_brief=model_brief,
        mental_model=mental_model,
    )
    fallback_grounding = grounding_validator.validate(file_path, fallback_claims, evidence_pack)
    fallback_grounded_claims = fallback_grounding.grounded_claims
    fallback_rejected_claims = fallback_grounding.rejected_claims

    try:
        discovered_claims = discovery_agent.discover(
            mental_model,
            evidence_pack,
            source_document=Path(file_path).name,
        )
        grounding = grounding_validator.validate(file_path, discovered_claims, evidence_pack)
        gpt_grounded_claims = grounding.grounded_claims
        gpt_rejected_claims = grounding.rejected_claims
    except WorkbookClaimDiscoveryUnavailable as exc:
        discovery_error = str(exc)
        extraction_mode = "fallback_deterministic_scaffold_llm_unavailable"

    discovery_comparison = _claim_discovery_comparison(
        gpt_claims=gpt_grounded_claims,
        fallback_claims=fallback_grounded_claims,
        gpt_rejected_claims=gpt_rejected_claims,
        fallback_rejected_claims=fallback_rejected_claims,
    )
    if extraction_mode == "gpt_claim_discovery" and gpt_grounded_claims:
        claims = _merge_claims_with_fallback(
            gpt_claims=gpt_grounded_claims,
            fallback_claims=fallback_grounded_claims,
        )
        rejected_claims = gpt_rejected_claims + fallback_rejected_claims
        if len(claims) > len(gpt_grounded_claims):
            extraction_mode = "gpt_claim_discovery_with_fallback_bridge"
    else:
        claims = fallback_grounded_claims
        rejected_claims = fallback_rejected_claims
        if extraction_mode == "gpt_claim_discovery":
            extraction_mode = "fallback_deterministic_scaffold_gpt_returned_no_grounded_claims"
            discovery_error = "GPT claim discovery returned no grounded claims."

    diagnostics = _claim_extraction_diagnostics(
        intake=intake,
        mental_model=mental_model.as_dict(),
        evidence_pack=evidence_pack.as_dict(),
        extraction_mode=extraction_mode,
        discovery_count=len(discovered_claims) if discovered_claims else len(fallback_claims),
        discovery_error=discovery_error,
        grounded_count=len(claims),
        rejected_claims=rejected_claims,
        discovery_comparison=discovery_comparison,
    )

    return WorkbookClaimExtractionResult(
        intake_result=intake.as_dict(),
        workbook_inspection=inspection.as_dict(),
        workbook_orientation=orientation.as_dict(),
        model_brief=model_brief.as_dict(),
        mental_model=mental_model.as_dict(),
        evidence_pack=evidence_pack.as_dict(),
        claims=claims,
        rejected_claims=rejected_claims,
        extraction_mode=extraction_mode,
        diagnostics=diagnostics,
        discovery_comparison=discovery_comparison,
    )


def run_financial_model_verification(file_path: str | Path) -> dict[str, Any]:
    """Run Day 5 Trust Engine verification for financial model claims.

    This returns verified facts and reconciliation notes. It does not run reasoning or
    produce recommendations.
    """
    claim_result = run_financial_model_claim_extraction(file_path)
    verifier = TrustVerifier()
    reconciliation_engine = ReconciliationEngine()

    verification_result: VerificationRunResult = verifier.verify_claims(
        file_path=file_path,
        claims=claim_result.claims,
        mental_model=claim_result.mental_model,
    )
    reconciliation_notes = reconciliation_engine.reconcile(verification_result.verified_facts)
    verification_result.reconciliation_notes.extend(reconciliation_notes)

    result = {
        "claim_result": claim_result.as_dict(),
        "verification": verification_result.as_dict(),
    }
    result["diagnostics"] = _verification_diagnostics(
        claim_diagnostics=claim_result.diagnostics or {},
        verification_summary=verification_result.summary,
        reconciliation_notes=reconciliation_notes,
    )
    return result


def _claim_extraction_diagnostics(
    intake: IntakeResult,
    mental_model: dict[str, Any],
    evidence_pack: dict[str, Any],
    extraction_mode: str,
    discovery_count: int,
    discovery_error: str | None,
    grounded_count: int,
    rejected_claims: list[dict[str, Any]],
    discovery_comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sampled_total = sum(len(items) for items in evidence_pack.get("sampled_cells", {}).values())
    rejection_reasons: dict[str, int] = {}
    for rejected in rejected_claims:
        for error in rejected.get("errors", []):
            rejection_reasons[error] = rejection_reasons.get(error, 0) + 1

    return {
        "intake": {
            "status": "passed" if intake.route.get("pipeline_name") == "financial_model_pipeline" else "failed",
            "document_type": intake.document_identity.get("document_type"),
            "route": intake.route.get("pipeline_name"),
            "human_review_required": intake.route.get("human_review_required", False),
        },
        "mental_model": {
            "status": "passed" if mental_model.get("important_sheets") else "needs_review",
            "important_sheets": mental_model.get("important_sheets", []),
            "expected_metric_families": mental_model.get("expected_metric_families", []),
            "likely_authoritative_sources": mental_model.get("likely_authoritative_sources", {}),
        },
        "evidence_pack": {
            "status": "passed" if sampled_total else "failed",
            "sheet_count": len(evidence_pack.get("important_sheet_names", [])),
            "sampled_cells_total": sampled_total,
            "candidate_neighborhoods": len(evidence_pack.get("candidate_neighborhoods", [])),
        },
        "claim_discovery": {
            "status": "fallback" if extraction_mode.startswith("fallback") else "passed",
            "mode": extraction_mode,
            "claims_returned": discovery_count,
            "gpt_unavailable_or_insufficient_reason": discovery_error,
            "comparison_summary": (discovery_comparison or {}).get("summary", {}),
        },
        "grounding": {
            "status": "passed" if grounded_count else ("failed" if discovery_count else "not_run"),
            "grounded_claims": grounded_count,
            "rejected_claims": len(rejected_claims),
            "rejection_reasons": rejection_reasons,
        },
    }


def _gpt_claims_insufficient(
    gpt_claims: list[dict[str, Any]],
    fallback_claims: list[dict[str, Any]],
) -> bool:
    if not gpt_claims:
        return True
    if not fallback_claims:
        return False
    threshold = max(3, int(len(fallback_claims) * 0.6))
    return len(gpt_claims) < threshold


def _merge_claims_with_fallback(
    gpt_claims: list[dict[str, Any]],
    fallback_claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep GPT-native claims primary and add fallback claims only for missing metrics."""
    merged = list(gpt_claims)
    gpt_keys = {_comparison_key(str(claim.get("metric_or_subject"))) for claim in gpt_claims}
    for fallback_claim in fallback_claims:
        key = _comparison_key(str(fallback_claim.get("metric_or_subject")))
        if key in gpt_keys:
            continue
        merged.append(fallback_claim)
        gpt_keys.add(key)
    return merged


def _claim_discovery_comparison(
    gpt_claims: list[dict[str, Any]],
    fallback_claims: list[dict[str, Any]],
    gpt_rejected_claims: list[dict[str, Any]],
    fallback_rejected_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    gpt_by_key = _claims_by_comparison_key(gpt_claims)
    fallback_by_key = _claims_by_comparison_key(fallback_claims)
    gpt_keys = set(gpt_by_key)
    fallback_keys = set(fallback_by_key)
    overlap_keys = sorted(gpt_keys & fallback_keys)
    missing_keys = sorted(fallback_keys - gpt_keys)
    gpt_only_keys = sorted(gpt_keys - fallback_keys)
    overlap = [_comparison_pair(key, gpt_by_key, fallback_by_key) for key in overlap_keys]
    missing_from_gpt = [_claim_summary(fallback_by_key[key]) for key in missing_keys]
    gpt_only = [_claim_summary(gpt_by_key[key]) for key in gpt_only_keys]
    return {
        "summary": {
            "gpt_native_claims": len(gpt_claims),
            "fallback_baseline_claims": len(fallback_claims),
            "overlap": len(overlap),
            "missing_from_gpt": len(missing_from_gpt),
            "gpt_only_claims": len(gpt_only),
            "gpt_rejected_claims": len(gpt_rejected_claims),
            "fallback_rejected_claims": len(fallback_rejected_claims),
        },
        "gpt_native_claims": [_claim_summary(claim) for claim in gpt_claims],
        "fallback_baseline_claims": [_claim_summary(claim) for claim in fallback_claims],
        "overlap": overlap,
        "missing_from_gpt": missing_from_gpt,
        "gpt_only_claims": gpt_only,
        "rejected": {
            "gpt": gpt_rejected_claims,
            "fallback": fallback_rejected_claims,
        },
    }


def _claims_by_comparison_key(claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _comparison_key(str(claim.get("metric_or_subject"))): claim
        for claim in claims
        if claim.get("metric_or_subject")
    }


def _comparison_key(metric_or_subject: str) -> str:
    normalized = "".join(
        char.lower() if char.isalnum() else "_"
        for char in metric_or_subject
    )
    words = [
        word for word in normalized.split("_")
        if word and word not in {"total", "amount", "required", "original"}
    ]
    return "_".join(words)


def _comparison_pair(
    key: str,
    gpt_by_key: dict[str, dict[str, Any]],
    fallback_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "comparison_key": key,
        "gpt": _claim_summary(gpt_by_key[key]),
        "fallback": _claim_summary(fallback_by_key[key]),
    }


def _claim_summary(claim: dict[str, Any]) -> dict[str, Any]:
    source_location = claim.get("source_location") or {}
    if isinstance(source_location, dict):
        source = source_location.get("cell")
        if source_location.get("row") and not source:
            source = f"row{source_location.get('row')}"
        source = f"{source_location.get('sheet')}!{source}" if source else source_location.get("sheet")
    else:
        source = source_location
    return {
        "metric_or_subject": claim.get("metric_or_subject"),
        "value": claim.get("value"),
        "unit": claim.get("unit"),
        "source": source,
        "confidence": claim.get("confidence"),
        "extraction_method": claim.get("extraction_method"),
    }


def _verification_diagnostics(
    claim_diagnostics: dict[str, Any],
    verification_summary: dict[str, Any],
    reconciliation_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    diagnostics = dict(claim_diagnostics)
    diagnostics["verification"] = {
        "status": "passed" if verification_summary.get("claims_total", 0) else "not_run",
        "summary": verification_summary,
    }
    diagnostics["reconciliation"] = {
        "status": "passed" if reconciliation_notes else "not_run",
        "notes_count": len(reconciliation_notes),
        "caveats": [note for note in reconciliation_notes if note.get("status") == "caveat"],
    }
    return diagnostics


def run_financial_model_reasoning(
    file_path: str | Path,
    question: str = "What does the verified financial model evidence show?",
) -> dict[str, Any]:
    """Run Day 6 reasoning from verified facts only.

    This is a readout, not a final investment recommendation.
    """
    verification_run = run_financial_model_verification(file_path)
    verification = verification_run["verification"]
    verified_facts = [
        fact for fact in verification["verified_facts"]
        if fact.get("verification_status") in {"verified", "verified_with_caveat"}
    ]
    reasoning_agent = ReasoningAgent()
    reasoning = reasoning_agent.reason(
        question=question,
        verified_facts=verified_facts,
        reconciliation_notes=verification.get("reconciliation_notes", []),
        context={
            "document_identity": verification_run["claim_result"]["intake_result"]["document_identity"],
            "mental_model": verification_run["claim_result"]["mental_model"],
            "verification_summary": verification["summary"],
        },
    )
    return {
        "verification_run": verification_run,
        "reasoning": reasoning,
    }


class MoosePipeline:
    """Coordinate Moose agents and the code Trust Engine."""

    # TODO(Day 1): This is an orchestration skeleton only. It must not be wired into Collie
    # production flow until each contract has tests and explicit integration approval.
    def __init__(
        self,
        file_identifier: FileIdentifier | None = None,
        workbook_orientation: WorkbookOrientationAgent | None = None,
        model_brief: ModelBriefAgent | None = None,
        claim_extractor: ClaimExtractor | None = None,
        trust_verifier: TrustVerifier | None = None,
        reasoning_agent: ReasoningAgent | None = None,
    ) -> None:
        self.file_identifier = file_identifier or FileIdentifier()
        self.workbook_orientation = workbook_orientation or WorkbookOrientationAgent()
        self.model_brief = model_brief or ModelBriefAgent()
        self.claim_extractor = claim_extractor or ClaimExtractor()
        self.trust_verifier = trust_verifier or TrustVerifier()
        self.reasoning_agent = reasoning_agent or ReasoningAgent()

    def run(self, file_path: str | Path, question: str | None = None) -> dict[str, Any]:
        """Run the intended Moose flow from upload to recommendation."""
        document_identity = self.identify_file(file_path)
        routed_pipeline = self.route_to_pipeline(document_identity)
        comprehension = self.run_comprehension(file_path, document_identity, routed_pipeline)
        claims = self.extract_claims(comprehension)
        verified_facts = self.verify_claims(claims)
        recommendation = self.reason_from_verified_facts(question, verified_facts)

        return {
            "document_identity": document_identity,
            "routed_pipeline": routed_pipeline,
            "comprehension": comprehension,
            "claims": claims,
            "verified_facts": verified_facts,
            "recommendation": recommendation,
        }

    def identify_file(self, file_path: str | Path) -> dict[str, Any]:
        """Identify file type and Moose work context."""
        return self.file_identifier.identify(file_path)

    def route_to_pipeline(self, document_identity: dict[str, Any]) -> str:
        """Route by the recommended pipeline from document identity."""
        # TODO(Day 2): Load routing rules from knowledge/routing_rules.yaml.
        if document_identity.get("human_review_required"):
            return "human_review"
        return str(document_identity.get("recommended_pipeline", "human_review"))

    def run_comprehension(
        self,
        file_path: str | Path,
        document_identity: dict[str, Any],
        routed_pipeline: str,
    ) -> dict[str, Any]:
        """Run the specialized comprehension step for the routed pipeline."""
        # TODO(Day 3+): Add document-specific comprehension stubs beyond workbook-like files.
        if routed_pipeline in {"financial_model_pipeline", "budget_workbook_pipeline", "fund_model_pipeline"}:
            orientation = self.workbook_orientation.orient(file_path, document_identity)
            return self.model_brief.create_brief(orientation)
        raise NotImplementedError(f"No Moose comprehension stub for {routed_pipeline}.")

    def extract_claims(self, comprehension: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract claims from the comprehension output."""
        return self.claim_extractor.extract(comprehension)

    def verify_claims(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Verify claims with the code Trust Engine."""
        return self.trust_verifier.verify_claims(claims)

    def reason_from_verified_facts(
        self,
        question: str | None,
        verified_facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Reason from verified facts only."""
        return self.reasoning_agent.reason(question or "What recommendation follows?", verified_facts)
