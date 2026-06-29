"""Moose Intake Layer.

Day 2 intake identifies files, resolves business context from knowledge files, and returns
routing metadata. It does not extract metrics, verify claims, call GPT, or execute pipelines.
"""

from .context_resolver import ContextResolver
from .file_identifier import FileIdentifier
from .intake_result import DocumentIdentity, IntakeResult
from .router import Router

__all__ = [
    "ContextResolver",
    "DocumentIdentity",
    "FileIdentifier",
    "IntakeResult",
    "Router",
]
