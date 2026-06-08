"""
RAG System - Main Entry Point
Hệ thống RAG với Short-term Memory Layer
Chỉ nhận đầu vào và đưa ra kết quả, tất cả chạy ngầm
"""

from typing import Any, Optional, List, Dict, Union
import json
from utils.logger import get_logger
from utils.langsmith_tracer import tracer
from modules.planner import plan
from modules.short_term_memory import retrieve_from_short_term_memory
from modules.retrieval import (
    retrieve_from_rag,
    retrieve_from_graph,
    retrieve_from_user_profile
)
from modules.total_info import aggregate_information
from modules.generation import generate_response

logger = get_logger(__name__)

SUPPORTED_INTENTS = {
    "HOTEL_FEATURE_QA",
    "HOTEL_POLICY_QA",
    "HOTEL_COMPARISON_QA",
}
DEFAULT_INTENT_TYPE = "HOTEL_FEATURE_QA"
DEFAULT_SOURCE = "RAG_SERVICE"


def _default_features() -> Dict[str, Any]:
    return {
        "hotel_name": "",
        "destination": "",
        "amenities": [],
        "expectations": [],
    }


def _normalize_rag_input(rag_input: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize input to the schema described in AGENTS.md.

    String input is still accepted for backward compatibility with the current CLI
    and tests, then wrapped into the structured RAG input schema.
    """
    if isinstance(rag_input, str):
        query = rag_input.strip()
        if not query:
            raise ValueError("Input query must not be empty")
        return {
            "intent_type": DEFAULT_INTENT_TYPE,
            "source": DEFAULT_SOURCE,
            "parameters": {
                "query": query,
                "features": _default_features(),
            },
        }

    if not isinstance(rag_input, dict):
        raise TypeError("RAG input must be a string or a dict following AGENTS.md")

    intent_type = rag_input.get("intent_type") or DEFAULT_INTENT_TYPE
    if intent_type not in SUPPORTED_INTENTS:
        raise ValueError(
            f"Unsupported intent_type: {intent_type}. "
            f"Supported intents: {sorted(SUPPORTED_INTENTS)}"
        )

    source = rag_input.get("source") or DEFAULT_SOURCE
    parameters = rag_input.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("RAG input must include parameters as an object")

    query = parameters.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("RAG input must include parameters.query as a non-empty string")

    features = parameters.get("features") or {}
    if not isinstance(features, dict):
        raise ValueError("RAG input parameters.features must be an object")

    normalized_features = _default_features()
    normalized_features.update(features)
    for list_key in ("amenities", "expectations"):
        value = normalized_features.get(list_key)
        if value is None:
            normalized_features[list_key] = []
        elif not isinstance(value, list):
            normalized_features[list_key] = [value]

    return {
        "intent_type": intent_type,
        "source": source,
        "parameters": {
            "query": query.strip(),
            "features": normalized_features,
        },
    }


class chatbot:
    """
    Hệ thống RAG chính.
    Interface đơn giản: input query -> output response
    """
    
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.conversation_history: List[Dict] = []
        logger.info(f"Chatbot initialized for user: {user_id}")
    
    @tracer.trace("rag_system_process")
    def process(
        self,
        query: Union[str, Dict[str, Any]],
        enable_short_term_memory: bool = True,
        enable_rag: bool = True,
        enable_graph: bool = True,
        enable_user_profile: bool = True,
        return_detailed: bool = False
    ) -> str:
        """
        Xử lý query và trả về response.
        
        Args:
            query: Query từ người dùng
            enable_short_term_memory: Sử dụng short-term memory
            enable_rag: Sử dụng RAG retrieval
            enable_graph: Sử dụng Graph retrieval
            enable_user_profile: Sử dụng User Profile retrieval
            return_detailed: Trả về chi tiết từng bước (cho debugging)
        
        Returns:
            Response text (hoặc dict nếu return_detailed=True)
        """
        try:
            normalized_input = _normalize_rag_input(query)
            query_text = normalized_input["parameters"]["query"]
            logger.info(f"Processing query: {query_text}")

            # Step 1: Planning
            logger.info("Step 1: Planning...")
            plan_result = plan(query_text)
            logger.info(f"Plan: {json.dumps(plan_result, ensure_ascii=False)}")
            
            # Step 2: Short-term Memory Retrieval
            short_term_memory_results = None
            if enable_short_term_memory and plan_result.get("needs_short_term_memory"):
                logger.info("Step 2: Retrieving from short-term memory...")
                short_term_memory_results = retrieve_from_short_term_memory(
                    query_text,
                    context=plan_result.get("context")
                )
                logger.info(f"Short-term memory: {short_term_memory_results}")
            
            # Step 3: Parallel Retrievals (RAG, Graph, User Profile)
            logger.info("Step 3: Parallel retrievals...")
            rag_results = None
            graph_results = None
            user_profile_results = None
            
            if enable_rag and plan_result.get("needs_rag"):
                logger.info("Retrieving from RAG...")
                rag_results = retrieve_from_rag(query_text)
            
            if enable_graph and plan_result.get("needs_graph"):
                logger.info("Retrieving from Graph...")
                graph_results = retrieve_from_graph(query_text)
            
            if enable_user_profile and plan_result.get("needs_user_profile"):
                logger.info("Retrieving from User Profile...")
                user_profile_results = retrieve_from_user_profile(self.user_id, query_text)
            
            # Step 4: Information Aggregation
            logger.info("Step 4: Aggregating information...")
            aggregated_result = aggregate_information(
                query_text,
                plan_result=plan_result,
                rag_results=rag_results,
                graph_results=graph_results,
                user_profile_results=user_profile_results,
                short_term_memory_results=short_term_memory_results
            )
            logger.info(f"Aggregation result: {aggregated_result}")
            
            # Step 5: Response Generation
            logger.info("Step 5: Generating response...")
            response = generate_response(
                query_text,
                aggregated_result.get("aggregated_info", ""),
                conversation_history=self.conversation_history
            )
            logger.info("Response generated successfully")
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": query_text})
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # Return result
            if return_detailed:
                return {
                    "input": normalized_input,
                    "query": query_text,
                    "response": response,
                    "plan": plan_result,
                    "short_term_memory": short_term_memory_results,
                    "rag": rag_results,
                    "graph": graph_results,
                    "user_profile": user_profile_results,
                    "aggregated_info": aggregated_result
                }
            else:
                return response
        
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            if return_detailed:
                return {
                    "query": query,
                    "response": f"Xin lỗi, có lỗi xảy ra: {str(e)}",
                    "error": str(e)
                }
            else:
                return f"Xin lỗi, có lỗi xảy ra: {str(e)}"
    
    def chat(self, query: Union[str, Dict[str, Any]]) -> str:
        """
        Giao diện chat đơn giản.
        
        Args:
            query: User query
        
        Returns:
            Response
        """
        return self.process(query, return_detailed=False)
    
    def clear_history(self):
        """Xóa conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")


# Global instance
_chatbot_instance: Optional[chatbot] = None

def get_chatbot(user_id: str = "default_user") -> chatbot:
    """
    Lấy instance của chatbot.
    
    Args:
        user_id: User ID
    
    Returns:
        chatbot instance
    """
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = chatbot(user_id)
    return _chatbot_instance


if __name__ == "__main__":
    # Example usage
    bot = get_chatbot(user_id="user_123")
    
    # Simple query
    query = "Hãy giúp tôi tìm hiểu về lịch sử công ty"
    response = bot.chat(query)
    print(f"\nQuery: {query}")
    print(f"Response: {response}")
    
    # Detailed response for debugging
    detailed_response = bot.process(query, return_detailed=True)
    print(f"\nDetailed Response: {json.dumps(detailed_response, ensure_ascii=False, indent=2)}")
