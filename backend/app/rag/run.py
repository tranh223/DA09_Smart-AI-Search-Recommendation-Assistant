"""
RAG System API
Dạng API cho hệ thống RAG
"""

from rag_system import chatbot, get_chatbot



class ChatbotAPI:
    """API wrapper cho Chatbot"""
    
    def __init__(self, user_id: str = "default_user"):
        self.system = get_chatbot(user_id)
    
    def ask(self, question: str) -> str:
        """
        Đặt câu hỏi và nhận câu trả lời.
        
        Example:
            api = ChatbotAPI()
            answer = api.ask("Hãy giúp tôi tìm hiểu về...")
        """
        return self.system.chat(question)
    
    def ask_detailed(self, question: str, include_debug: bool = False) -> dict:
        """
        Đặt câu hỏi với chi tiết.
        """
        return self.system.process(question, return_detailed=True)
    
    def clear_memory(self):
        """Xóa conversation history"""
        self.system.clear_history()


# Simple interactive CLI
def interactive_cli():
    """Giao diện CLI tương tác"""
    import sys
    
    print("=" * 60)
    print("Chatbot - Interactive Mode")
    print("=" * 60)
    
    # Get user ID
    user_id = input("Enter User ID (or press Enter for default): ").strip() or "default_user"
    
    api = ChatbotAPI(user_id)
    print(f"\nWelcome, {user_id}!")
    print("Type 'exit' to quit, 'clear' to clear history\n")
    
    while True:
        try:
            query = input("You: ").strip()
            
            if not query:
                continue
            
            if query.lower() == "exit":
                print("Goodbye!")
                break
            
            if query.lower() == "clear":
                api.clear_memory()
                print("Conversation history cleared.\n")
                continue
            
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
