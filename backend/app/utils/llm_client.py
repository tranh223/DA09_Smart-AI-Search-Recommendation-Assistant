"""OpenAI LLM client for the RAG module."""

from __future__ import annotations

import json
import os
from typing import Any
from dotenv import load_dotenv
from utils.logger import get_logger
load_dotenv()
logger = get_logger(__name__)

# Defaults are conservative fallbacks; runtime config should come from .env.
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TEMPERATURE = 0.9
_DEFAULT_MAX_TOKENS = 12000
_DEFAULT_TIMEOUT_SECONDS = 30.0

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except Exception as _exc:  # pragma: no cover
    _OpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_AVAILABLE = False
    _OPENAI_IMPORT_ERROR = _exc


class LLMClient:
    """OpenAI LLM client used by the RAG pipeline."""

    def __init__(self) -> None:
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            logger.warning("[LLMClient] OPENAI_API_KEY not set — LLM calls will fail.")

        if not _OPENAI_AVAILABLE:
            raise RuntimeError(
                "OpenAI Python SDK not installed. Run: pip install openai"
            )

        self._client = _OpenAI(
            api_key=openai_api_key,
            base_url=os.getenv("OPENAI_CHAT_BASE_URL") or os.getenv("BASE_URL"),
        )
        self.model = os.getenv("LLM_MODEL", _DEFAULT_MODEL)
        self.temperature = float(os.getenv("RAG_LLM_TEMPERATURE", str(_DEFAULT_TEMPERATURE)) or _DEFAULT_TEMPERATURE)
        self.max_tokens = int(os.getenv("RAG_LLM_MAX_TOKENS", str(_DEFAULT_MAX_TOKENS)) or _DEFAULT_MAX_TOKENS)
        self.timeout_seconds = float(
            os.getenv("RAG_LLM_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS)))
            or _DEFAULT_TIMEOUT_SECONDS
        )

    def call(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        **_kwargs: Any,
    ) -> str:
        """Call the OpenAI chat completion API."""
        full_messages: list[dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        logger.info("[LLMClient] Calling OpenAI model=%s", self.model)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout_seconds,
        )
        result = response.choices[0].message.content
        logger.info("[LLMClient] Call successful.")
        return result

    def call_with_structured_output(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call and parse JSON response. Returns {"raw": ...} on parse failure."""
        response = self.call(messages, system_prompt, **kwargs)
        try:
            return json.loads(response)
        except Exception:
            return {"raw": response}


llm_client = LLMClient()
