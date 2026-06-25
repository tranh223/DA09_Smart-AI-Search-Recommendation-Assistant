from dataclasses import dataclass
from enum import StrEnum


class GuardrailReason(StrEnum):
    OTA_QUERY = "OTA_QUERY"
    ASSISTANT_HELP = "ASSISTANT_HELP"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(slots=True)
class GuardrailRequest:
    query: str


@dataclass(slots=True)
class GuardrailResponse:
    passed: bool
    reason: GuardrailReason
