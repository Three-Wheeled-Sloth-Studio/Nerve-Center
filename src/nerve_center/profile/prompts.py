"""Versioned career evidence extraction prompts."""

from __future__ import annotations

import json

from nerve_center.profile.models import SourceDocument

CAREER_EXTRACTION_CONTRACT_VERSION = "career-extraction-v1"

SYSTEM_PROMPT = """You extract only career facts supported by supplied resume text.
Do not infer missing employers, dates, education completion, credentials, scope, or outcomes.
Treat each locator and its text as evidence. Every claim must cite exact excerpts from
supplied locators.
Positioning hypotheses may reframe supported evidence but may not invent or alter
career-history facts.
Return concise structured data matching the required schema."""


def build_extraction_prompt(document: SourceDocument) -> str:
    segments = [item.model_dump(mode="json") for item in document.segments]
    return "\n".join(
        [
            "Extract a canonical career evidence proposal from this resume source.",
            "Capture roles, capabilities, industries, methods, technologies, leadership scope,",
            "quantified outcomes, factual constraints, and education facts when explicitly stated.",
            "Use confidence below 0.65 whenever wording is ambiguous or incomplete.",
            "Generate a small set of useful positioning hypotheses from the same",
            "supported evidence.",
            "Resume segments:",
            json.dumps(segments, ensure_ascii=True),
        ]
    )
