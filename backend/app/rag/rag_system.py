"""
RAG System - Main Entry Point
Hệ thống RAG với Short-term Memory Layer
Chỉ nhận đầu vào và đưa ra kết quả, tất cả chạy ngầm
"""

from typing import Optional, List, Dict
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
        query: str,
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
        logger.info(f"Processing query: {query}")
        
        try:
            # Step 1: Planning
            logger.info("Step 1: Planning...")
            plan_result = plan(query)
            logger.info(f"Plan: {json.dumps(plan_result, ensure_ascii=False)}")
            
            # Step 2: Short-term Memory Retrieval
            short_term_memory_results = None
            if enable_short_term_memory and plan_result.get("needs_short_term_memory"):
                logger.info("Step 2: Retrieving from short-term memory...")
                short_term_memory_results = retrieve_from_short_term_memory(
                    query,
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
                rag_results = retrieve_from_rag(query)
            
            if enable_graph and plan_result.get("needs_graph"):
                logger.info("Retrieving from Graph...")
                graph_results = retrieve_from_graph(query)
            
            if enable_user_profile and plan_result.get("needs_user_profile"):
                logger.info("Retrieving from User Profile...")
                user_profile_results = retrieve_from_user_profile(self.user_id, query)
            
            # Step 4: Information Aggregation
            logger.info("Step 4: Aggregating information...")
            aggregated_result = aggregate_information(
                query,
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
                query,
                aggregated_result.get("aggregated_info", ""),
                conversation_history=self.conversation_history
            )
            logger.info("Response generated successfully")
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # Return result
            if return_detailed:
                return {
                    "query": query,
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
    
    def chat(self, query: str) -> str:
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
