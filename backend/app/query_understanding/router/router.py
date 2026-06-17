from dataclasses import asdict

from query_understanding.enums import GraphOperation, SearchSource, SearchTask
from query_understanding.models.intent import IntentResult
from query_understanding.models.planner import ActiveProfile, SearchPlanResult, SessionContext
from query_understanding.models.router import ExecutionStep, RagExecutionStep, RouterResult


class Router:
    def run(
        self,
        query: str,
        search_plan: SearchPlanResult,
        intent: IntentResult,
        active_profile: ActiveProfile,
        session_context: SessionContext,
        user_id: str,
    ) -> RouterResult:
        search_tasks = list(search_plan.search_tasks) or self._derive_legacy_tasks(search_plan)
        rag_plan, recommendation_plan = self._build_execution_plans(
            query=query,
            search_tasks=search_tasks,
            intent=intent,
            active_profile=active_profile,
            session_context=session_context,
            user_id=user_id,
        )
        return RouterResult(
            execution_mode=search_plan.execution_mode,
            rag_plan=rag_plan,
            recommendation_plan=recommendation_plan,
        )

    def _build_execution_plans(
        self,
        query: str,
        search_tasks: list[SearchTask | str],
        intent: IntentResult,
        active_profile: ActiveProfile,
        session_context: SessionContext,
        user_id: str,
    ) -> tuple[list[RagExecutionStep], list[ExecutionStep]]:
        rag_plan: list[RagExecutionStep] = []
        recommendation_plan: list[ExecutionStep] = []
        rag_step = 1
        rec_step = 1
        recommendation_parameters = self._build_recommendation_parameters(
            active_profile=active_profile,
            session_context=session_context,
            user_id=user_id,
        )

        for raw_task in search_tasks:
            task = SearchTask(raw_task)
            if task in {SearchTask.INFORMATION, SearchTask.SPECIAL_FEATURE, SearchTask.HOTEL_SIMILAR}:
                rag_plan.append(
                    RagExecutionStep(
                        step=rag_step,
                        intent_type=task,
                        source="RAG_SERVICE",
                        parameters=self._build_rag_parameters(
                            query,
                            task,
                            intent,
                            active_profile,
                            session_context,
                        ),
                    )
                )
                rag_step += 1
                continue

            if task == SearchTask.HOTEL_SEARCH:
                recommendation_plan.append(
                    ExecutionStep(
                        step=rec_step,
                        intent_type=task,
                        source=SearchSource.HOTEL_EMBEDDING_DB,
                        parameters=recommendation_parameters,
                    )
                )
                rec_step += 1
                continue

            if task == SearchTask.TRENDING:
                recommendation_plan.append(
                    ExecutionStep(
                        step=rec_step,
                        intent_type=task,
                        source=SearchSource.UNIFIED_GRAPH,
                        parameters=recommendation_parameters,
                    )
                )
                rec_step += 1
                continue

            if task == SearchTask.PERSONALIZATION:
                recommendation_plan.append(
                    ExecutionStep(
                        step=rec_step,
                        intent_type=task,
                        source=SearchSource.UNIFIED_GRAPH,
                        graph_operation=GraphOperation.SIMILAR_USER_SEARCH,
                        parameters=recommendation_parameters,
                    )
                )
                rec_step += 1
                continue

            raise ValueError(f"Unsupported search task: {task}")

        return rag_plan, recommendation_plan

    def _build_constraints(
        self,
        intent: IntentResult,
        active_profile: ActiveProfile,
        session_context: SessionContext,
    ) -> dict[str, object]:
        entities = intent.entities
        constraints = intent.constraints
        return {
            "destination": entities.destination or session_context.destination,
            "nearby_place": entities.nearby_place or session_context.nearby_place or constraints.location_hint,
            "tags": list(active_profile.long_term_preference_habits),
            "amenities": list(active_profile.long_term_amenities),
            "hotel_types": list(active_profile.long_term_hotel_types),
            "room_views": list(active_profile.long_term_room_views),
            "budget": {
                "min": entities.budget_min,
                "max": entities.budget_max,
            },
            "check_in": entities.check_in or session_context.check_in,
            "check_out": entities.check_out or session_context.check_out,
            "trip_type": entities.trip_type,
            "number_of_guests": (
                entities.number_of_guests
                if entities.number_of_guests is not None
                else session_context.number_of_guests
            ),
        }

    def _build_search_context(
        self,
        intent: IntentResult,
        active_profile: ActiveProfile,
        session_context: SessionContext,
    ) -> dict[str, object]:
        constraints = self._build_constraints(intent, active_profile, session_context)
        graph_context = self._build_graph_context(intent, active_profile, session_context, constraints)
        return {
            "constraints": constraints,
            "graph_context": graph_context,
        }

    def _build_rag_parameters(
        self,
        query: str,
        task: SearchTask,
        intent: IntentResult,
        active_profile: ActiveProfile,
        session_context: SessionContext,
    ) -> dict[str, object]:
        return {
            "query": query,
            "features": self._build_rag_features(task, intent, active_profile, session_context),
        }

    def _build_rag_features(
        self,
        task: SearchTask,
        intent: IntentResult,
        active_profile: ActiveProfile,
        session_context: SessionContext,
    ) -> dict[str, object]:
        entities = intent.entities
        constraints = intent.constraints
        features: dict[str, object] = {
            "hotel_name": "",
            "destination": "",
            "amenities": [],
            "expectations": [],
        }

        if task == SearchTask.HOTEL_SIMILAR:
            hotel_names = [name for name in [entities.hotel_name] if name]
            if hotel_names:
                features["hotel_names"] = hotel_names
        elif entities.hotel_name:
            features["hotel_name"] = entities.hotel_name

        destination = entities.destination or session_context.destination
        if destination:
            features["destination"] = destination

        amenities = list(active_profile.long_term_amenities)
        if amenities:
            features["amenities"] = list(amenities)

        expectations = self._build_expectations(intent, active_profile)
        if expectations:
            features["expectations"] = expectations

        return features

    def _build_expectations(self, intent: IntentResult, active_profile: ActiveProfile) -> list[str]:
        trip_type = intent.entities.trip_type
        mapping = {
            "family": "family_trip",
            "couple": "couple_trip",
            "business": "business_trip",
            "solo": "solo_trip",
            "tourist": "tourist_trip",
            "group": "group_trip",
            "Cặp đôi": "couple_trip",
            "Gia đình có thanh thiếu niên": "family_trip",
            "Gia đình có trẻ nhỏ": "family_trip",
            "Khách du lịch một mình": "solo_trip",
            "Khách đi công tác": "business_trip",
            "Nhóm du khách": "group_trip",
        }
        expectation = mapping.get(trip_type or "")
        return [expectation] if expectation else []

    def _map_rag_intent_type(self, task: SearchTask, query: str) -> str:
        if task == SearchTask.HOTEL_SIMILAR:
            return "HOTEL_COMPARISON_QA"
        if task == SearchTask.SPECIAL_FEATURE:
            return "HOTEL_FEATURE_QA"
        normalized_query = query.lower()
        policy_markers = (
            "chinh sach",
            "đặt phòng",
            "dat phong",
            "booking",
            "refund",
            "hoan",
            "huy",
            "check-in",
            "check in",
            "check-out",
            "check out",
        )
        if any(marker in normalized_query for marker in policy_markers):
            return "HOTEL_POLICY_QA"
        return "HOTEL_DESCRIPTION_QA"

    def _build_graph_context(
        self,
        intent: IntentResult,
        active_profile: ActiveProfile,
        session_context: SessionContext,
        constraints: dict[str, object],
    ) -> dict[str, object]:
        params: dict[str, object] = {}
        destination = intent.entities.destination or session_context.destination
        if destination:
            params["destination"] = destination
        if intent.entities.hotel_name:
            params["hotel_name"] = intent.entities.hotel_name
        if constraints["nearby_place"]:
            params["nearby_place"] = constraints["nearby_place"]
        if constraints["budget"]["min"] is not None or constraints["budget"]["max"] is not None:
            params["budget"] = constraints["budget"]
        if constraints["check_in"]:
            params["check_in"] = constraints["check_in"]
        if constraints["check_out"]:
            params["check_out"] = constraints["check_out"]
        if constraints["trip_type"]:
            params["trip_type"] = constraints["trip_type"]
        if constraints["number_of_guests"] is not None:
            params["number_of_guests"] = constraints["number_of_guests"]
        if constraints["amenities"]:
            params["amenities"] = list(constraints["amenities"])
        if constraints["hotel_types"]:
            params["hotel_types"] = list(constraints["hotel_types"])
        if constraints["tags"]:
            params["tags"] = list(constraints["tags"])
        if constraints["room_views"]:
            params["room_views"] = list(constraints["room_views"])
        return params

    def _build_recommendation_parameters(
        self,
        *,
        active_profile: ActiveProfile,
        session_context: SessionContext,
        user_id: str,
    ) -> dict[str, object]:
        return {
            "user_id": user_id,
            "active_profile": asdict(active_profile),
            "session_context": self._build_recommendation_session_context(session_context),
        }

    @staticmethod
    def _build_recommendation_session_context(session_context: SessionContext) -> dict[str, object]:
        return {
            "destination": session_context.destination,
            "current_location": session_context.current_location,
            "nearby_place": session_context.nearby_place,
            "number_of_guests": session_context.number_of_guests,
            "has_pet": session_context.has_pet,
            "has_children": session_context.has_children,
            "check_in": session_context.check_in,
            "check_out": session_context.check_out,
            "note_amenities": session_context.note_amenities,
            "session_price_range": asdict(session_context.session_price_range),
            "runtime_tag_expansion": asdict(session_context.runtime_tag_expansion),
        }

    @staticmethod
    def _top_count_key(values: dict[str, object]) -> str | None:
        if not values:
            return None
        return max(values.items(), key=lambda item: getattr(item[1], "count", 0))[0]

    def _build_personalization_params(self, search_context: dict[str, object], user_id: str) -> dict[str, object]:
        params = dict(search_context["graph_context"])
        params["constraints"] = dict(search_context["constraints"])
        params["user_id"] = user_id
        return params

    def _derive_legacy_tasks(self, search_plan: SearchPlanResult) -> list[SearchTask]:
        tasks: list[SearchTask] = []
        if "RAG_SEARCH" in search_plan.retrieval_sources:
            tasks.append(SearchTask.INFORMATION)
        if "HOTEL_EMBEDDING_SEARCH" in search_plan.retrieval_sources:
            tasks.append(SearchTask.HOTEL_SEARCH)
        if GraphOperation.SIMILAR_USER_SEARCH in search_plan.graph_operations:
            tasks.append(SearchTask.PERSONALIZATION)
        if GraphOperation.HOTEL_SIMILARITY_SEARCH in search_plan.graph_operations:
            tasks.append(SearchTask.HOTEL_SIMILAR)
        if GraphOperation.HOTEL_FEATURE_DISCOVERY in search_plan.graph_operations:
            tasks.append(SearchTask.SPECIAL_FEATURE)
        return list(dict.fromkeys(tasks))
