import os
from openai import OpenAI
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class LLMClient:
    """Client để gọi LLM từ nhiều nguồn API OpenAI."""
    
    def __init__(self):
        self.primary_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.backup_client = OpenAI(api_key=settings.OPENAI_API_KEY_BACKUP) if settings.OPENAI_API_KEY_BACKUP else None
        self.model = settings.OPENAI_MODEL
        self.temperature = settings.OPENAI_TEMPERATURE
        self.max_tokens = settings.OPENAI_MAX_TOKENS
    
    def call(self, messages: list, system_prompt: str = None, use_backup: bool = False) -> str:
        """
        Gọi LLM với prompt đầy đủ.
        
        Args:
            messages: List các message từ user
            system_prompt: System prompt để thiết lập context
            use_backup: Sử dụng backup API key
        
        Returns:
            Response text từ LLM
        """
        try:
            client = self.backup_client if (use_backup and self.backup_client) else self.primary_client
            
            # Thêm system prompt nếu có
            full_messages = []
            if system_prompt:
                full_messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            full_messages.extend(messages)
            
            logger.info(f"Calling LLM with model {self.model}")
            
            response = client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            result = response.choices[0].message.content
            logger.info("LLM call successful")
            return result
            
        except Exception as e:
            logger.error(f"Error calling primary LLM: {str(e)}")
            
            # Fallback to backup nếu có
            if not use_backup and self.backup_client:
                logger.info("Trying backup API key...")
                return self.call(messages, system_prompt, use_backup=True)
            
            raise
    
    def call_with_structured_output(self, messages: list, system_prompt: str = None) -> dict:
        """Gọi LLM và trả về structured JSON response."""
        response = self.call(messages, system_prompt)
        try:
            import json
            return json.loads(response)
        except:
            return {"raw": response}

llm_client = LLMClient()
