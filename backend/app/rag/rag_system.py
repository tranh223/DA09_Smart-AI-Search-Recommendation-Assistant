"""
RAG System - Main Entry Point
Chỉ gồm: Planner -> (RAG, Graph, Hotel SQL) -> aggregate_information -> generate_response
Chỉ sử dụng dữ liệu khách sạn từ RAG, Graph và Hotel SQL.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional
import json

from rag_input import (
    RAGRequest,
    build_retrieval_query,
    build_structured_plan,
    parse_rag_request,
)
from utils.logger import get_logger
from utils.langsmith_tracer import tracer

from modules.planner import plan
from modules.retrieval import (
    resolve_hotel_entity,
    retrieve_from_graph,
    retrieve_from_hotel_sql,
    retrieve_from_rag,
)
from modules.skill_agent import route_intent
from modules.total_info import aggregate_information
from modules.generation import generate_response

logger = get_logger(__name__)


def _entity_resolution_response(resolution: dict[str, Any]) -> str:
    candidates = resolution.get("candidates") or []
    if resolution.get("status") == "ambiguous" and candidates:
        names = ", ".join(
            str(candidate.get("hotel_name"))
            for candidate in candidates[:3]
            if candidate.get("hotel_name")
        )
        return (
            "Không thể xác định duy nhất khách sạn từ tên đã cung cấp. "
            f"Các kết quả gần nhất: {names}."
        )
    return "Không tìm thấy khách sạn phù hợp với tên và điểm đến đã cung cấp."


class chatbot:
    """Main RAG system."""

    def __init__(self):
        logger.info("Hotel RAG chatbot initialized")

    @tracer.trace("rag_system_process")
    def process(
        self,
        query: str | dict[str, Any] | RAGRequest,
        enable_rag: bool = True,
        enable_graph: bool = True,
        return_detailed: bool = False,
    ) -> str:
        structured_request = (
            parse_rag_request(query) if isinstance(query, (dict, RAGRequest)) else None
        )
        user_query = (
            structured_request.parameters.query if structured_request else str(query)
        )
        retrieval_query = (
            build_retrieval_query(structured_request) if structured_request else user_query
        )
        logger.info(f"Processing query: {user_query}")

        try:
            # Step 1: Planning
            logger.info("Step 1: Planning...")
            plan_result = (
                build_structured_plan(structured_request)
                if structured_request
                else plan(user_query)
            )
            try:
                logger.info(f"Plan: {json.dumps(plan_result, ensure_ascii=False)}")
            except Exception:
                logger.info("Plan: <unserializable>")

            # Structured input already contains routing and extracted entities.
            if structured_request:
                skill_result = structured_request.model_dump()
            else:
                try:
                    skill_result = route_intent(user_query)
                    logger.info(f"Skill agent: {json.dumps(skill_result, ensure_ascii=False)}")
                except Exception as e:
                    logger.warning(f"Skill agent failed, continue without routing: {e}")
                    skill_result = {}

            # Step 2: Retrievals (RAG, Graph, Hotel SQL)
            logger.info("Step 2: Retrieving (RAG, Graph, Hotel SQL)...")

            # Be robust to planner output missing/typoed keys.
            needs_rag = plan_result.get("needs_rag", True)
            needs_graph = plan_result.get("needs_graph", True)
            needs_hotel_sql = plan_result.get("needs_hotel_sql", True)

            logger.info(
                "Planner needs flags: "
                f"needs_rag={needs_rag}, needs_graph={needs_graph}, needs_hotel_sql={needs_hotel_sql}"
            )

            rag_results = None
            graph_results = None
            hotel_sql_results = None
            entity_resolution = None

            if structured_request:
                features = structured_request.parameters.features
                rag_filters = {
                    "section": plan_result.get("rag_sections", []),
                }
                resolved_hotel_id = None
                resolved_hotel_name = features.hotel_name
                if features.hotel_name:
                    entity_resolution = resolve_hotel_entity(
                        features.hotel_name,
                        features.destination,
                    )
                    if entity_resolution.get("status") == "resolved":
                        resolved_hotel_id = entity_resolution.get("hotel_id")
                        resolved_hotel_name = entity_resolution.get("canonical_name")
                        rag_filters["hotel_id"] = resolved_hotel_id
                    else:
                        logger.warning(
                            "Hotel entity was not uniquely resolved: %s",
                            entity_resolution,
                        )

                jobs = {}
                with ThreadPoolExecutor(max_workers=3) as executor:
                    entity_ready = not features.hotel_name or resolved_hotel_id is not None
                    if enable_rag and needs_rag and entity_ready:
                        jobs["rag"] = executor.submit(
                            retrieve_from_rag,
                            retrieval_query,
                            5,
                            rag_filters,
                        )
                    if enable_graph and needs_graph and entity_ready:
                        graph_query = retrieval_query
                        if resolved_hotel_id is not None:
                            graph_query += f"\nCanonical hotel_id: {resolved_hotel_id}"
                        jobs["graph"] = executor.submit(
                            retrieve_from_graph,
                            graph_query,
                            5,
                            resolved_hotel_id,
                        )
                    if needs_hotel_sql and entity_ready:
                        jobs["hotel_sql"] = executor.submit(
                            retrieve_from_hotel_sql,
                            user_query,
                            plan_result.get("hotel_sql_needs"),
                            hotel_id=resolved_hotel_id,
                            hotel_name=resolved_hotel_name,
                            city=features.destination,
                        )

                    rag_results = jobs["rag"].result() if "rag" in jobs else None
                    graph_results = jobs["graph"].result() if "graph" in jobs else None
                    hotel_sql_results = (
                        jobs["hotel_sql"].result() if "hotel_sql" in jobs else None
                    )
                    if features.hotel_name and not entity_ready:
                        resolution_error = {
                            "success": False,
                            "count": 0,
                            "error": "Hotel name could not be uniquely resolved",
                            "entity_resolution": entity_resolution,
                        }
                        if needs_rag:
                            rag_results = {"source": "rag", "results": [], **resolution_error}
                        if needs_graph:
                            graph_results = {"source": "graph", "results": [], **resolution_error}
                        if needs_hotel_sql:
                            hotel_sql_results = {
                                "source": "hotel_sql",
                                "results": None,
                                **resolution_error,
                            }
                        response = _entity_resolution_response(entity_resolution)
                        if return_detailed:
                            return {
                                "query": user_query,
                                "input": structured_request.model_dump(),
                                "retrieval_query": retrieval_query,
                                "response": response,
                                "plan": plan_result,
                                "skill_agent": skill_result,
                                "entity_resolution": entity_resolution,
                                "rag": rag_results,
                                "graph": graph_results,
                                "hotel_sql": hotel_sql_results,
                                "aggregated_info": None,
                            }
                        return response
            else:
                if enable_rag and needs_rag:
                    rag_results = retrieve_from_rag(user_query)
                if enable_graph and needs_graph:
                    graph_results = retrieve_from_graph(user_query)
                if needs_hotel_sql:
                    hotel_sql_results = retrieve_from_hotel_sql(user_query)

            # Step 3: Information Aggregation
            logger.info("Step 3: Aggregating information...")
            aggregated_result = aggregate_information(
                user_query,
                plan_result=plan_result,
                rag_results=rag_results,
                graph_results=graph_results,
                hotel_sql_results=hotel_sql_results,
                single_pass=structured_request is not None,
            )
            logger.info(f"Aggregation result: {aggregated_result}")

            # Step 4: Response Generation
            logger.info("Step 4: Generating response...")
            response = generate_response(
                user_query,
                aggregated_result.get("aggregated_info", ""),
            )
            logger.info("Response generated successfully")

            if return_detailed:
                return {
                    "query": user_query,
                    "input": structured_request.model_dump() if structured_request else query,
                    "retrieval_query": retrieval_query,
                    "response": response,
                    "plan": plan_result,
                    "skill_agent": skill_result,
                    "entity_resolution": entity_resolution,
                    "rag": rag_results,
                    "graph": graph_results,
                    "hotel_sql": hotel_sql_results,
                    "aggregated_info": aggregated_result,
                }

            return response

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            if return_detailed:
                return {
                    "query": user_query,
                    "response": f"Xin lỗi, có lỗi xảy ra: {str(e)}",
                    "error": str(e),
                }
            return f"Xin lỗi, có lỗi xảy ra: {str(e)}"

    def chat(self, query: str | dict[str, Any] | RAGRequest) -> str:
        return self.process(query, return_detailed=False)

# Global instance
_chatbot_instance: Optional[chatbot] = None


def get_chatbot() -> chatbot:
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = chatbot()
    return _chatbot_instance

