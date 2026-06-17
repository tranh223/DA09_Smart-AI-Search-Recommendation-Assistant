from query_understanding.router.schema import RouterRequest, RouterResponse


class RouterService:
    def run(self, request: RouterRequest) -> RouterResponse:
        raise NotImplementedError("RouterService is a Phase 1 contract stub.")
