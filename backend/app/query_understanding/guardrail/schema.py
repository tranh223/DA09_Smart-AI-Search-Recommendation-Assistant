from dataclasses import dataclass
from enum import StrEnum


class GuardrailReason(StrEnum):
    OTA_QUERY = "OTA_QUERY"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNSAFE_QUERY = "UNSAFE_QUERY"


@dataclass(slots=True)
class GuardrailRequest:
    query: str


@dataclass(slots=True)
class GuardrailResponse:
    passed: bool
    reason: GuardrailReason
