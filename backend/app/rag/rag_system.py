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

            # Step 1.6: Auxiliary entity intent extraction (hotel names)
            try:
                from modules.planner_intents_aux import parse_aux_intents

                aux_intents = parse_aux_intents(query)
                logger.info(
                    "Aux intents: "
                    f"{json.dumps(aux_intents, ensure_ascii=False) if isinstance(aux_intents, dict) else aux_intents}"
                )
            except Exception as e:
                logger.warning(f"Aux intents extraction failed: {e}")
                aux_intents = {}

            # Step 1.7: Standardize tool inputs for planner schema completeness
            # Ensures planner output always contains tool_inputs even if planner LLM didn't.
            try:
                from modules.planner_intent_toolschema import build_tool_inputs_from_context

                std_tool_inputs = build_tool_inputs_from_context(
                    query=query,
                    plan_result=plan_result,
                    aux_intents=aux_intents,
                )
                plan_result["tool_inputs"] = std_tool_inputs.get("tools", plan_result.get("tool_inputs", {}))
            except Exception as e:
                logger.warning(f"Failed to build standardized tool inputs: {e}")



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

            # Ensure aggregate_information receives dicts (avoid None type issues)
            rag_results = rag_results if rag_results is not None else {"success": False, "source": "rag", "results": [], "count": 0}
            graph_results = graph_results if graph_results is not None else {"success": False, "source": "graph", "results": [], "count": 0}
            hotel_sql_results = hotel_sql_results if hotel_sql_results is not None else {"success": False, "source": "hotel_sql", "results": None, "count": 0}

            # Build hotel_sql tool inputs from planner entities
            # Tool input for Hotel SQL is driven by entities from planner/aux intent,
            # not by raw query text as the primary selector.
            tool_inputs = plan_result.get("tool_inputs") if isinstance(plan_result, dict) else None
            hotel_sql_entities = []
            hotel_sql_need = None
            if isinstance(tool_inputs, dict):
                hsql = tool_inputs.get("hotel_sql")
                if isinstance(hsql, dict):
                    hotel_sql_entities = hsql.get("hotel_ids") or []
                    hotel_sql_need = hsql.get("need")

            # Override `query` passed to hotel sql tool with entity ids when available.
            # If no entities found, fallback to original query.
            hotel_sql_selector = ""
            if hotel_sql_entities:
                hotel_sql_selector = "hotel_id=" + ",".join(str(x) for x in hotel_sql_entities)

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

                # Select hotel sql based on entity ids from planner/tool_inputs when available.
                # If we found entities -> pass selector text to hotel_sql_utils best-effort extractor.
                sql_query = query
                if hotel_sql_selector:
                    sql_query = hotel_sql_selector

                hotel_sql_results = retrieve_from_hotel_sql(sql_query)
                logger.info(f"hotel_sql_results: {hotel_sql_results}")


            # Step 2.5: Use extracted entities to refine context (if any)
            if isinstance(aux_intents, dict):
                # Inject into aggregation plan_result context field
                try:
                    plan_result.setdefault("context", "")
                    extra_ctx = aux_intents.get("hotel_entity_intent", {})
                    plan_result["context"] = (
                        plan_result.get("context", "")
                        + f"\n[Hotel Entities Extracted] {extra_ctx}"
                    )
                except Exception:
                    pass

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

