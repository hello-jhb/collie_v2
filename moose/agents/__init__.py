"""Moose agent stubs.

These classes define the first architecture contracts. They intentionally do not make
production GPT calls or reuse Collie's deterministic extractors.
"""

from .claim_extractor import ClaimExtractor
from .file_identifier import FileIdentifier
from .model_brief import ModelBriefAgent
from .reasoning import ReasoningAgent
from .workbook_orientation import WorkbookOrientationAgent

__all__ = [
    "ClaimExtractor",
    "FileIdentifier",
    "ModelBriefAgent",
    "ReasoningAgent",
    "WorkbookOrientationAgent",
]
