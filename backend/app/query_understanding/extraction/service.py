from query_understanding.extraction.schema import ExtractionRequest, ExtractionResponse


class ExtractionService:
    def run(self, request: ExtractionRequest) -> ExtractionResponse:
        raise NotImplementedError("ExtractionService is a Phase 1 contract stub.")
