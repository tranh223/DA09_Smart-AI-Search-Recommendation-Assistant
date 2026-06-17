import os
from openai import OpenAI
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

class LLMClient:
    """Unified LLM client: OpenAI primary/backup + optional Groq provider."""

    def __init__(self):
        # Provider can be selected by env var. If LLM_PROVIDER=groq, avoid initializing OpenAI clients.
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()

        self.primary_client = None
        self.backup_client = None

        if self.provider == "openai":
            # Lazy init to avoid hard-failing when OPENAI key is missing.
            if settings.OPENAI_API_KEY:
                self.primary_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.backup_client = (
                OpenAI(api_key=settings.OPENAI_API_KEY_BACKUP)
                if settings.OPENAI_API_KEY_BACKUP
                else None
            )

        # OpenAI defaults
        self.model = settings.OPENAI_MODEL
        self.temperature = settings.OPENAI_TEMPERATURE
        self.max_tokens = settings.OPENAI_MAX_TOKENS

        # Groq optional
        self.groq_api_key = getattr(settings, "GROQ_API_KEY", "")
        self.groq_model = getattr(settings, "GROQ_MODEL", "llama3-8b-8192")
        self.groq_temperature = getattr(settings, "GROQ_TEMPERATURE", self.temperature)
        self.groq_max_tokens = getattr(settings, "GROQ_MAX_TOKENS", self.max_tokens)

    def call(
        self,
        messages: list,
        system_prompt: str = None,
        use_backup: bool = False,
        provider: str = os.getenv("LLM_PROVIDER", "openai"),
    ) -> str:

        """
        Gọi LLM với prompt đầy đủ.
        """
        provider = (provider or self.provider or "openai").lower()

        try:
            if provider == "groq":
                if not self.groq_api_key:
                    raise RuntimeError("GROQ_API_KEY not configured in environment")

                from utils.llm_client_groq import GroqClient, GroqConfig

                groq_client = GroqClient(
                    GroqConfig(
                        api_key=self.groq_api_key,
                        model=self.groq_model,
                        temperature=self.groq_temperature,
                        max_tokens=self.groq_max_tokens,
                    )
                )
                logger.info(f"Calling Groq with model {self.groq_model}")
                return groq_client.call(messages=messages, system_prompt=system_prompt or "")


            # If provider isn't groq, we are using OpenAI.
            client = self.backup_client if (use_backup and self.backup_client) else self.primary_client
            if client is None:
                raise RuntimeError("OpenAI credentials are missing. Set OPENAI_API_KEY or set LLM_PROVIDER=groq with GROQ_API_KEY.")


            
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
    
    def call_with_structured_output(self, messages: list, system_prompt: str = None, provider: str = "openai") -> dict:

        """Gọi LLM và trả về structured JSON response."""
        response = self.call(messages, system_prompt, provider=provider)

        try:
            import json
            return json.loads(response)
        except:
            return {"raw": response}

llm_client = LLMClient()
