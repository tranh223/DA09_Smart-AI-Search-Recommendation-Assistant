"""Unified LLM client for OpenAI and Groq providers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from config.settings import settings
from utils.logger import get_logger

try:
    from openai import OpenAI as _OpenAI
except Exception as exc:  # pragma: no cover - import availability depends on env
    _OpenAI = None
    _OPENAI_IMPORT_ERROR = exc


logger = get_logger(__name__)


@dataclass
class GroqConfig:
    api_key: str
    model: str = "llama3-8b-8192"
    temperature: float = 0.9
    max_tokens: int = 2000


class GroqClient:
    def __init__(self, cfg: GroqConfig):
        self.cfg = cfg
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from groq import Groq  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Groq Python SDK not installed. Install `groq` in requirements.txt."
            ) from exc

        self._client = Groq(api_key=self.cfg.api_key)
        return self._client

    def call(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> str:
        full_messages: list[dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        client = self._get_client()
        response = client.chat.completions.create(
            model=self.cfg.model,
            messages=full_messages,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        return response.choices[0].message.content

    def call_with_structured_output(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        raw = self.call(messages, system_prompt)
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw}


class LLMClient:
    """Unified LLM client: OpenAI primary/backup + optional Groq provider."""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()

        self.primary_client = None
        self.backup_client = None

        if self.provider == "openai":
            if settings.OPENAI_API_KEY:
                self.primary_client = self._build_openai_client(settings.OPENAI_API_KEY)
            self.backup_client = (
                self._build_openai_client(settings.OPENAI_API_KEY_BACKUP)
                if settings.OPENAI_API_KEY_BACKUP
                else None
            )

        self.model = settings.OPENAI_MODEL
        self.temperature = settings.OPENAI_TEMPERATURE
        self.max_tokens = settings.OPENAI_MAX_TOKENS

        self.groq_api_key = getattr(settings, "GROQ_API_KEY", "")
        self.groq_model = getattr(settings, "GROQ_MODEL", "llama3-8b-8192")
        self.groq_temperature = getattr(settings, "GROQ_TEMPERATURE", self.temperature)
        self.groq_max_tokens = getattr(settings, "GROQ_MAX_TOKENS", self.max_tokens)

    def _build_openai_client(self, api_key: str):
        if _OpenAI is None:
            raise RuntimeError("OpenAI Python SDK not installed. Install `openai` in requirements.txt.") from _OPENAI_IMPORT_ERROR
        return _OpenAI(api_key=api_key)

    def call(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        use_backup: bool = False,
        provider: str = os.getenv("LLM_PROVIDER", "openai"),
    ) -> str:
        """Call the configured LLM provider with a full message list."""

        provider = (provider or self.provider or "openai").lower()

        try:
            if provider == "groq":
                if not self.groq_api_key:
                    raise RuntimeError("GROQ_API_KEY not configured in environment")

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

            client = self.backup_client if (use_backup and self.backup_client) else self.primary_client
            if client is None:
                raise RuntimeError(
                    "OpenAI credentials are missing. Set OPENAI_API_KEY or set LLM_PROVIDER=groq with GROQ_API_KEY."
                )

            full_messages: list[dict[str, str]] = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)

            logger.info(f"Calling LLM with model {self.model}")

            response = client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            result = response.choices[0].message.content
            logger.info("LLM call successful")
            return result

        except Exception as exc:
            logger.error(f"Error calling primary LLM: {str(exc)}")

            if not use_backup and self.backup_client:
                logger.info("Trying backup API key...")
                return self.call(messages, system_prompt, use_backup=True)

            raise

    def call_with_structured_output(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        provider: str = "openai",
    ) -> dict[str, Any]:
        """Call the configured LLM and parse the response as JSON when possible."""

        response = self.call(messages, system_prompt, provider=provider)

        try:
            return json.loads(response)
        except Exception:
            return {"raw": response}


llm_client = LLMClient()
