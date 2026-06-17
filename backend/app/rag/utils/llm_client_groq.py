"""Groq LLM client adapter.

This project currently calls OpenAI via `openai.OpenAI` in utils/llm_client.py.
To add Groq as an alternative provider, we provide a compatible wrapper
that supports:
- call(messages, system_prompt, model, temperature, max_tokens)
- call_with_structured_output(messages, system_prompt)

Environment variables expected (add to .env):
- GROQ_API_KEY
- GROQ_MODEL (optional)

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

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
        except Exception as e:
            raise RuntimeError(
                "Groq Python SDK not installed. Install `groq` in requirements.txt."
            ) from e

        self._client = Groq(api_key=self.cfg.api_key)
        return self._client

    def call(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        full_messages: List[Dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.cfg.model,
            messages=full_messages,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )

        return resp.choices[0].message.content

    def call_with_structured_output(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw = self.call(messages, system_prompt)
        try:
            import json

            return json.loads(raw)
        except Exception:
            return {"raw": raw}

