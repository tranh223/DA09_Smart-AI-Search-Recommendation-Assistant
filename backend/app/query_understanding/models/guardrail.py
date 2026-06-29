from dataclasses import dataclass


@dataclass(slots=True)
class GuardrailResult:
    allow: bool
    category: str
    reason: str = ""
    assistant_help_context_mode: str = "NONE"
