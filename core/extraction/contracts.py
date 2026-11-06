"""Stable domain contracts for later LLM extractors. No external requests in M04-A."""
from dataclasses import dataclass, field
from typing import Protocol, Literal

from core.extraction.catalog import FIELD_LABELS


@dataclass(frozen=True)
class SourceSegment:
    id: int
    document_id: int
    location: str
    text: str

@dataclass(frozen=True)
class CandidateFact:
    field_key: str
    value_text: str
    segment_id: int
    evidence_quote: str
    origin: str
    confidence: float | None = None

class Extractor(Protocol):
    """Future LLM providers must implement this interface.
    Each candidate must cite a provided segment and verbatim supporting quote.
    The backend rechecks citations. The extractor cannot mark facts verified.
    """
    def extract(self, segments: list[SourceSegment]) -> list[CandidateFact]: ...

class MockExtractor:
    """No hallucinated demonstration facts. Real facts require a source segment."""
    def extract(self, segments: list[SourceSegment]) -> list[CandidateFact]:
        return []
