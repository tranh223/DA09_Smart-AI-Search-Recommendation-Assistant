from query_understanding.planner.schema import (
    SearchPlanCheckRequest,
    SearchPlanCheckResponse,
    SearchPlannerRequest,
    SearchPlannerResponse,
)


class SearchPlanCheckService:
    def run(self, request: SearchPlanCheckRequest) -> SearchPlanCheckResponse:
        raise NotImplementedError("SearchPlanCheckService is a Phase 1 contract stub.")


class SearchPlannerService:
    def run(self, request: SearchPlannerRequest) -> SearchPlannerResponse:
        raise NotImplementedError("SearchPlannerService is a Phase 1 contract stub.")
