"""
RAG System API
Dạng API cho hệ thống RAG
"""

from typing import Any

from rag_system import chatbot, get_chatbot



class ChatbotAPI:
    """API wrapper cho Chatbot"""
    
    def __init__(self):
        self.system = get_chatbot()
    
    def ask(self, question: str | dict[str, Any]) -> str:
        """
        Đặt câu hỏi và nhận câu trả lời.
        
        Example:
            api = ChatbotAPI()
            answer = api.ask("Hãy giúp tôi tìm hiểu về...")
        """
        return self.system.chat(question)
    
    def ask_detailed(
        self,
        question: str | dict[str, Any],
        include_debug: bool = False,
    ) -> dict:
        """
        Đặt câu hỏi với chi tiết.
        """
        return self.system.process(question, return_detailed=True)
    
# Simple interactive CLI
def interactive_cli():
    """Giao diện CLI tương tác"""
    import sys
    
    print("=" * 60)
    print("Chatbot - Interactive Mode")
    print("=" * 60)
    
    api = ChatbotAPI()
    print("Type 'exit' to quit\n")
    
    while True:
        try:
            query = input("You: ").strip()
            
            if not query:
                continue
            
            if query.lower() == "exit":
                print("Goodbye!")
                break
            
            print("\nProcessing...\n")
            response = api.ask(query)
            print(f"Assistant: {response}\n")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {str(e)}\n")


if __name__ == "__main__":
    interactive_cli()
