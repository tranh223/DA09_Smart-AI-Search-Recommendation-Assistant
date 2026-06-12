"""
RAG System - Main Entry Point
Chỉ gồm: Planner -> (RAG, Graph, Hotel SQL) -> aggregate_information -> generate_response
Short-term Memory và User Profile đã bị loại bỏ khỏi pipeline.
"""

from __future__ import annotations

from typing import Optional, List, Dict
import json

from utils.logger import get_logger
from utils.langsmith_tracer import tracer

from modules.planner import plan
from modules.retrieval import retrieve_from_rag, retrieve_from_graph, retrieve_from_hotel_sql
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
        query: str,
        enable_rag: bool = True,
        enable_graph: bool = True,
        return_detailed: bool = False,
    ) -> str:
        logger.info(f"Processing query: {query}")

        try:
            # Step 1: Planning
            logger.info("Step 1: Planning...")
            plan_result = plan(query)
            try:
                logger.info(f"Plan: {json.dumps(plan_result, ensure_ascii=False)}")
            except Exception:
                logger.info("Plan: <unserializable>")

            # Step 1.5: Skill agent routing (best-effort)
            try:
                skill_result = route_intent(query)
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

            if enable_rag and needs_rag:
                logger.info("Retrieving from RAG...")
                rag_results = retrieve_from_rag(query)
                logger.info(f"rag_results: {rag_results}")

            if enable_graph and needs_graph:
                logger.info("Retrieving from Graph...")
                graph_results = retrieve_from_graph(query)
                logger.info(f"graph_results: {graph_results}")

            if needs_hotel_sql:
                logger.info("Retrieving from Hotel SQL...")
                hotel_sql_results = retrieve_from_hotel_sql(query)
                logger.info(f"hotel_sql_results: {hotel_sql_results}")

            # Step 3: Information Aggregation
            logger.info("Step 3: Aggregating information...")
            aggregated_result = aggregate_information(
                query,
                plan_result=plan_result,
                rag_results=rag_results,
                graph_results=graph_results,
                user_profile_results=None,
                short_term_memory_results=None,
                hotel_sql_results=hotel_sql_results,
            )
            logger.info(f"Aggregation result: {aggregated_result}")

            # Step 4: Response Generation
            logger.info("Step 4: Generating response...")
            response = generate_response(
                query,
                aggregated_result.get("aggregated_info", ""),
                conversation_history=self.conversation_history,
            )
            logger.info("Response generated successfully")

            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": response})

            if return_detailed:
                return {
                    "query": query,
                    "response": response,
                    "plan": plan_result,
                    "skill_agent": skill_result,
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
                    "query": query,
                    "response": f"Xin lỗi, có lỗi xảy ra: {str(e)}",
                    "error": str(e),
                }
            return f"Xin lỗi, có lỗi xảy ra: {str(e)}"

    def chat(self, query: str) -> str:
        return self.process(query, return_detailed=False)

    def clear_history(self) -> None:
        self.conversation_history = []
        logger.info("Conversation history cleared")


# Global instance
_chatbot_instance: Optional[chatbot] = None


def get_chatbot(user_id: str = "default_user") -> chatbot:
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = chatbot(user_id)
    return _chatbot_instance

