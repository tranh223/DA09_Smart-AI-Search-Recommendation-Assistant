import json
import os

from query_understanding.enums import SearchTask
from query_understanding.llm import OpenAIResponsesClient
from query_understanding.models.planner import SearchPlanResult
from query_understanding.planner.prompts import SEARCH_PLANNER_PROMPT


SEARCH_PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["search_tasks"],
    "properties": {
        "search_tasks": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    SearchTask.INFORMATION.value,
                    SearchTask.HOTEL_SIMILAR.value,
                    SearchTask.TRENDING.value,
                    SearchTask.HOTEL_SEARCH.value,
                    SearchTask.PERSONALIZATION.value,
                    SearchTask.SPECIAL_FEATURE.value,
                ],
            },
        }
    },
}


class SearchPlanner:
    def __init__(
        self,
        client: OpenAIResponsesClient | None = None,
        model: str | None = None,
    ) -> None:
        self.client = client or OpenAIResponsesClient()
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.last_trace: dict[str, object] = {}

    def run(self, query: str, conversation_history: list[dict[str, str]] | None = None) -> SearchPlanResult:
        normalized_history = self._normalize_history(conversation_history)
        payload = self.client.create_structured_output(
            model=self.model,
            instructions=SEARCH_PLANNER_PROMPT,
            input_text=self._build_input_text(
                query=query,
                conversation_history=normalized_history,
            ),
            schema_name="search_plan_result",
            schema=SEARCH_PLAN_SCHEMA,
        )
        self.last_trace = {
            "path": "llm",
            "model": self.model,
            "payload": payload,
        }

        tasks = self._dedupe_tasks(payload["search_tasks"])
        if not tasks:
            tasks = [SearchTask.INFORMATION]

        return SearchPlanResult(
            execution_mode="parallel",
            search_tasks=tasks,
        )

    @staticmethod
    def _dedupe_tasks(values: list[str]) -> list[SearchTask]:
        ordered: list[SearchTask] = []
        seen: set[SearchTask] = set()
        for value in values:
            task = SearchTask(value)
            if task in seen:
                continue
            seen.add(task)
            ordered.append(task)
        return ordered

    @staticmethod
    def _normalize_history(conversation_history: list[dict[str, str]] | None) -> list[dict[str, str]]:
        if not conversation_history:
            return []
        normalized: list[dict[str, str]] = []
        for item in conversation_history[-10:]:
            user_query = str(item.get("user_query", "")).strip()
            llm_answer = str(item.get("llm_answer", "")).strip()
            if not user_query and not llm_answer:
                continue
            normalized.append(
                {
                    "user_query": user_query,
                    "llm_answer": llm_answer,
                }
            )
        return normalized

    @staticmethod
    def _build_input_text(
        *,
        query: str,
        conversation_history: list[dict[str, str]],
    ) -> str:
        payload = {
            "query": query,
            "conversation_history": conversation_history,
        }
        return json.dumps(payload, ensure_ascii=False)
