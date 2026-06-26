"""RAG System - main entry point."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import json

from utils.logger import get_logger

try:
    from app.rag.utils.langsmith_tracer import tracer
    from app.rag.trace_utils import rag_trace, rag_trace_error
except Exception:  # pragma: no cover - standalone app/rag script mode
    from utils.langsmith_tracer import tracer
    from trace_utils import rag_trace, rag_trace_error

from modules.planner import plan
from modules.retrieval import retrieve_from_graph, retrieve_from_rag

from modules.skill_agent import route_intent
from modules.total_info import aggregate_information
from modules.generation import generate_response


logger = get_logger(__name__)


class chatbot:
    """Main RAG system."""

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.conversation_history: List[Dict] = []
        logger.info(f"Chatbot initialized for user: {user_id}")

    @tracer.trace("rag_system_process")
    def process(
        self,
        query: str | dict[str, Any],
        enable_rag: bool = True,
        enable_graph: bool = True,
        return_detailed: bool = False,
    ) -> str | dict[str, Any]:
        logger.info(f"Processing query: {query}")

        try:
            rag_trace(
                step="rag_system:input",
                input={"query": query, "enable_rag": enable_rag, "enable_graph": enable_graph},
            )

            original_query: str | dict[str, Any] = query
            retrieval_query: str | dict[str, Any] = query
            structured_request = None

            if isinstance(query, dict):
                from rag_input import (
                    build_retrieval_query,
                    build_structured_plan,
                    parse_rag_request,
                )

                structured_request = parse_rag_request(query)
                original_query = structured_request.parameters.query
                retrieval_query = build_retrieval_query(structured_request)
                logger.info(f"Structured request normalized to query: {original_query}")
            else:
                original_query = str(query)
                retrieval_query = original_query

            logger.info("Step 1: Planning...")
            if structured_request is not None:
                plan_result = build_structured_plan(structured_request)
            else:
                plan_result = plan(str(original_query))

            rag_trace(
                step="rag_system:planner",
                input={"structured": structured_request is not None},
                output=plan_result,
            )

            try:
                logger.info(f"Plan: {json.dumps(plan_result, ensure_ascii=False)}")
            except Exception:
                logger.info("Plan: <unserializable>")

            try:
                skill_result = route_intent(str(original_query))
                logger.info(f"Skill agent: {json.dumps(skill_result, ensure_ascii=False)}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Skill agent failed, continue without routing: {exc}")
                rag_trace_error(
                    step="rag_system:skill_agent",
                    error=exc,
                    input={"query": str(original_query)},
                )
                skill_result = {}
            rag_trace(
                step="rag_system:skill_agent",
                input={"query": str(original_query)},
                output=skill_result,
            )

            try:
                from modules.planner_intents_aux import parse_aux_intents

                aux_intents = parse_aux_intents(str(retrieval_query))
                logger.info(
                    "Aux intents: "
                    f"{json.dumps(aux_intents, ensure_ascii=False) if isinstance(aux_intents, dict) else aux_intents}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Aux intents extraction failed: {exc}")
                rag_trace_error(
                    step="rag_system:aux_intents",
                    error=exc,
                    input={"query": str(retrieval_query)},
                )
                aux_intents = {}
            rag_trace(
                step="rag_system:aux_intents",
                input={"query": str(retrieval_query)},
                output=aux_intents,
            )

            try:
                from modules.planner_intent_toolschema import build_tool_inputs_from_context

                std_tool_inputs = build_tool_inputs_from_context(
                    query=str(retrieval_query),
                    plan_result=plan_result,
                    aux_intents=aux_intents,
                )
                if isinstance(plan_result, dict):
                    plan_result["tool_inputs"] = std_tool_inputs.get(
                        "tools",
                        plan_result.get("tool_inputs", {}),
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Failed to build standardized tool inputs: {exc}")
                rag_trace_error(
                    step="rag_system:tool_inputs",
                    error=exc,
                    input={"query": str(retrieval_query)},
                )

            rag_trace(
                step="rag_system:tool_inputs",
                input={"query": str(retrieval_query)},
                output=(plan_result.get("tool_inputs") if isinstance(plan_result, dict) else None),
            )

            logger.info("Step 2: Retrieving (RAG, Graph, Hotel SQL)...")

            needs_rag = plan_result.get("needs_rag", True)
            needs_graph = plan_result.get("needs_graph", True)
            needs_hotel_sql = plan_result.get("needs_hotel_sql", True)

            rag_trace(
                step="rag_system:retrieval_plan_flags",
                input={
                    "needs_rag": needs_rag,
                    "needs_graph": needs_graph,
                    "needs_hotel_sql": needs_hotel_sql,
                },
                output={},
            )

            logger.info(
                "Planner needs flags: "
                f"needs_rag={needs_rag}, needs_graph={needs_graph}, needs_hotel_sql={needs_hotel_sql}"
            )

            rag_results = {"success": False, "source": "rag", "results": [], "count": 0}
            graph_results = {"success": False, "source": "graph", "results": [], "count": 0}
            hotel_sql_results = {"success": False, "source": "hotel_sql", "results": None, "count": 0}


            tool_inputs = plan_result.get("tool_inputs") if isinstance(plan_result, dict) else None
            hotel_sql_entities: list[Any] = []
            hotel_sql_need = None
            if isinstance(tool_inputs, dict):
                hsql = tool_inputs.get("hotel_sql")
                if isinstance(hsql, dict):
                    hotel_sql_entities = hsql.get("hotel_ids") or []
                    hotel_sql_need = hsql.get("need")

            hotel_sql_selector = ""
            if hotel_sql_entities:
                hotel_sql_selector = "hotel_id=" + ",".join(str(x) for x in hotel_sql_entities)
            elif structured_request is not None:
                hotel_name = structured_request.parameters.features.hotel_name
                if hotel_name:
                    hotel_sql_selector = hotel_name

            if enable_rag and needs_rag:
                logger.info("Retrieving from RAG...")
                rag_trace(step="rag_system:rag_retrieve:input", input={"query": str(retrieval_query)})
                rag_results = retrieve_from_rag(str(retrieval_query))
                rag_trace(step="rag_system:rag_retrieve:output", output=rag_results)
                logger.info(f"rag_results: {rag_results}")

            if enable_graph and needs_graph:
                logger.info("Retrieving from Graph...")
                rag_trace(step="rag_system:graph_retrieve:input", input={"query": str(retrieval_query)})
                graph_results = retrieve_from_graph(str(retrieval_query))
                rag_trace(step="rag_system:graph_retrieve:output", output=graph_results)
                logger.info(f"graph_results: {graph_results}")

            # Hotel Ask is handled via FAISS in RAG path.
            # Hotel SQL tool is removed from backend/rag.
            if needs_hotel_sql:
                logger.info("Skipping Hotel SQL retrieval (removed). Hotel Ask uses FAISS vector search.")


            if isinstance(aux_intents, dict):
                try:
                    plan_result.setdefault("context", "")
                    extra_ctx = aux_intents.get("hotel_entity_intent", {})
                    plan_result["context"] = (
                        plan_result.get("context", "")
                        + f"\n[Hotel Entities Extracted] {extra_ctx}"
                    )
                except Exception:
                    pass

            logger.info("Step 3: Aggregating information...")
            rag_trace(
                step="rag_system:aggregate:input",
                input={
                    "rag_ok": bool(rag_results and rag_results.get("success")),
                    "graph_ok": bool(graph_results and graph_results.get("success")),
                    "hotel_sql_ok": bool(hotel_sql_results and hotel_sql_results.get("success")),
                },
                output={},
            )

            aggregated_result = aggregate_information(
                str(original_query),
                plan_result=plan_result,
                rag_results=rag_results,
                graph_results=graph_results,
                user_profile_results={},
                short_term_memory_results={},
            )
            logger.info(f"Aggregation result: {aggregated_result}")
            rag_trace(step="rag_system:aggregate:output", output=aggregated_result)

            logger.info("Step 4: Generating response...")
            rag_trace(
                step="rag_system:generation:input",
                input={
                    "query": str(original_query),
                    "aggregated_info_len": len(str(aggregated_result.get("aggregated_info", ""))),
                    "history_len": len(self.conversation_history),
                },
            )
            response = generate_response(
                str(original_query),
                aggregated_result.get("aggregated_info", ""),
                conversation_history=self.conversation_history,
            )
            logger.info("Response generated successfully")
            rag_trace(
                step="rag_system:generation:output",
                output={"response": response, "response_len": len(response)},
            )

            self.conversation_history.append({"role": "user", "content": str(original_query)})
            self.conversation_history.append({"role": "assistant", "content": response})

            if return_detailed:
                return {
                    "query": str(original_query),
                    "retrieval_query": str(retrieval_query),
                    "response": response,
                    "plan": plan_result,
                    "skill_agent": skill_result,
                    "aux_intents": aux_intents,
                    "rag": rag_results,
                    "graph": graph_results,
                    "hotel_sql": hotel_sql_results,
                    "aggregated_info": aggregated_result,
                }

            return response

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error processing query: {str(exc)}", exc_info=True)
            rag_trace_error(
                step="rag_system:process",
                error=exc,
                input={"query": query, "return_detailed": return_detailed},
            )
            if return_detailed:
                return {
                    "query": str(query),
                    "response": "",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            return f"Xin loi, co loi xay ra: {str(exc)}"

    def chat(self, query: str) -> str:
        return self.process(query, return_detailed=False)  # type: ignore[return-value]

    def clear_history(self) -> None:
        self.conversation_history = []
        logger.info("Conversation history cleared")


_chatbot_instance: Optional[chatbot] = None


def get_chatbot(user_id: str = "default_user") -> chatbot:
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = chatbot(user_id)
    return _chatbot_instance
