"""Provider-agnostic extraction contract; no network calls in M04-B."""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class ExtractionInput:
    project_id: int
    segments: list[dict]  # id/document_id/location/content; retrieval layer controls context size
    field_catalog_version: str = 'vc-core-1'

@dataclass(frozen=True)
class ExtractionCandidate:
    field_key: str
    value: str
    segment_id: int
    verbatim_quote: str
    derivation: str = 'source_claim'  # source_claim|calculated|inferred
    rationale: str = ''

class StructuredExtractor(Protocol):
    def extract(self, request: ExtractionInput) -> list[ExtractionCandidate]: ...

class EvidenceVerifier(Protocol):
    def verify(self, candidate: ExtractionCandidate, sources: list[dict]) -> dict: ...

class DisabledExtractor:
    """Safe default: never fabricates facts, never makes outgoing requests."""
    def extract(self, request: ExtractionInput) -> list[ExtractionCandidate]:
        return []

def validate_candidate(candidate: ExtractionCandidate, segments: list[dict]) -> bool:
    from core.extraction.catalog import FIELD_BY_KEY
    by_id={int(s['id']):s for s in segments}
    source=by_id.get(candidate.segment_id)
    return bool(source and candidate.field_key in FIELD_BY_KEY and
                candidate.verbatim_quote and candidate.verbatim_quote in source['content'] and
                candidate.derivation in ('source_claim','calculated','inferred'))
