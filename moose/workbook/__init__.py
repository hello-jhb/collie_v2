"""Moose workbook comprehension.

Day 3 workbook comprehension inspects workbook structure, orients the workbook, and
produces a model brief. It does not extract metrics, verify claims, or call GPT.
"""

from .model_brief import ModelBriefBuilder
from .claim_extractor import FallbackWorkbookClaimExtractor, WorkbookClaimExtractor
from .discovery_agent import WorkbookClaimDiscoveryAgent, WorkbookClaimDiscoveryUnavailable
from .evidence_pack import WorkbookEvidencePackBuilder
from .grounding import WorkbookClaimGroundingValidator
from .mental_model import WorkbookMentalModelBuilder
from .workbook_inspector import WorkbookInspector
from .workbook_orientation import WorkbookOrientationBuilder
from .workbook_result import (
    ClaimGroundingResult,
    WorkbookEvidencePackResult,
    WorkbookClaimExtractionResult,
    ModelBriefResult,
    WorkbookComprehensionResult,
    WorkbookInspectionResult,
    WorkbookMentalModelResult,
    WorkbookOrientationResult,
)

__all__ = [
    "ModelBriefBuilder",
    "ModelBriefResult",
    "ClaimGroundingResult",
    "FallbackWorkbookClaimExtractor",
    "WorkbookClaimExtractionResult",
    "WorkbookClaimDiscoveryAgent",
    "WorkbookClaimDiscoveryUnavailable",
    "WorkbookClaimExtractor",
    "WorkbookComprehensionResult",
    "WorkbookEvidencePackBuilder",
    "WorkbookEvidencePackResult",
    "WorkbookClaimGroundingValidator",
    "WorkbookInspectionResult",
    "WorkbookInspector",
    "WorkbookMentalModelBuilder",
    "WorkbookMentalModelResult",
    "WorkbookOrientationBuilder",
    "WorkbookOrientationResult",
]
