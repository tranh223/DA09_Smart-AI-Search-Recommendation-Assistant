from query_understanding.guardrail.schema import GuardrailRequest, GuardrailResponse


class GuardrailService:
    def run(self, request: GuardrailRequest) -> GuardrailResponse:
        raise NotImplementedError("GuardrailService is a Phase 1 contract stub.")
