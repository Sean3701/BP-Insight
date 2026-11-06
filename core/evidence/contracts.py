"""Verification provider hook. No external lookups are performed in M04-A."""
from dataclasses import dataclass
from typing import Protocol
@dataclass(frozen=True)
class VerificationResult:
    assertion_id: int
    status: str  # unverified | supported | contradicted | indeterminate
    source_url: str | None = None
    checked_at: str | None = None
    notes: str = ""
class Verifier(Protocol):
    def verify(self, assertion_id: int) -> VerificationResult: ...
