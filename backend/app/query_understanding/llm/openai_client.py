import json
import os
import time
import hashlib
from typing import Any
from urllib import error, request
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

load_dotenv()

class OpenAIResponsesClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_delay_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = (
            base_url
            or os.getenv("OPENAI_RESPONSES_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1/responses"
        )
        self.timeout_seconds = timeout_seconds or float(os.getenv("LLM_TIMEOUT_SECONDS", "60") or "60")
        self.max_retries = max_retries if max_retries is not None else int(os.getenv("LLM_MAX_RETRIES", "2") or "2")
        self.retry_delay_seconds = (
            retry_delay_seconds
            if retry_delay_seconds is not None
            else float(os.getenv("LLM_RETRY_DELAY_SECONDS", "1.0") or "1.0")
        )
        self.prompt_cache_enabled = os.getenv("LLM_PROMPT_CACHE_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.prompt_cache_min_tokens = int(os.getenv("LLM_PROMPT_CACHE_MIN_TOKENS", "1024") or "1024")
        self.prompt_cache_retention = os.getenv("LLM_PROMPT_CACHE_RETENTION", "in_memory") or "in_memory"
        self.last_response_meta: dict[str, Any] = {}
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM-backed query understanding.")

    def create_structured_output(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
        safety_identifier: str | None = None,
        strict: bool = True,
        prompt_cache_key: str | None = None,
        prompt_cache_retention: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": input_text,
                        }
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": strict,
                }
            },
        }
        if safety_identifier:
            payload["safety_identifier"] = safety_identifier
        if prompt_cache_key:
            payload["prompt_cache_key"] = prompt_cache_key
        if prompt_cache_retention:
            payload["prompt_cache_retention"] = prompt_cache_retention
        if temperature is not None:
            payload["temperature"] = temperature

        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self.base_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        raw = self._execute_request_with_retry(http_request)

        parsed = json.loads(raw)
        self.last_response_meta = self._build_response_meta(
            payload=payload,
            parsed=parsed,
        )
        if parsed.get("error"):
            raise RuntimeError(f"OpenAI Responses API returned an error: {parsed['error']}")

        if parsed.get("status") == "incomplete":
            raise RuntimeError(
                f"OpenAI response incomplete: {parsed.get('incomplete_details') or 'unknown reason'}"
            )

        text_output = self._extract_output_text(parsed)
        try:
            return json.loads(text_output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model returned non-JSON structured output: {text_output}") from exc

    def build_prompt_cache_settings(
        self,
        *,
        component_name: str,
        model: str,
        instructions: str,
        schema_name: str,
        schema: dict[str, Any],
        strict: bool,
        min_tokens: int | None = None,
    ) -> dict[str, Any]:
        static_prompt = json.dumps(
            {
                "instructions": instructions,
                "schema_name": schema_name,
                "schema": schema,
                "strict": strict,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        estimated_tokens = self.estimate_tokens(static_prompt)
        threshold = self.prompt_cache_min_tokens if min_tokens is None else min_tokens
        eligible = self.prompt_cache_enabled and estimated_tokens >= threshold
        fingerprint = hashlib.sha256(
            f"{component_name}\n{model}\n{static_prompt}".encode("utf-8")
        ).hexdigest()[:16]
        cache_key = f"{component_name}:{model}:{fingerprint}"
        return {
            "enabled": eligible,
            "component": component_name,
            "estimated_static_tokens": estimated_tokens,
            "min_tokens": threshold,
            "prompt_cache_key": cache_key if eligible else None,
            "prompt_cache_retention": self.prompt_cache_retention if eligible else None,
        }

    def _execute_request_with_retry(self, http_request: request.Request) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                    return response.read().decode("utf-8")
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"OpenAI Responses API request failed: {exc.code} {details}") from exc
            except error.URLError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"Unable to reach OpenAI Responses API: {exc.reason}") from exc
            except (TimeoutError, ConnectionResetError, OSError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"OpenAI Responses API connection failed: {exc}") from exc
            time.sleep(self.retry_delay_seconds * (attempt + 1))

        raise RuntimeError(f"OpenAI Responses API request failed after retries: {last_error}")

    @staticmethod
    def _extract_output_text(payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        refusal_chunks: list[str] = []
        text_chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                content_type = content.get("type")
                if content_type == "refusal":
                    refusal_chunks.append(content.get("refusal", ""))
                if content_type in {"output_text", "text"} and isinstance(content.get("text"), str):
                    text_chunks.append(content["text"])

        if text_chunks:
            return "".join(text_chunks)
        if refusal_chunks:
            raise RuntimeError(f"Model refused the request: {' '.join(refusal_chunks).strip()}")
        raise RuntimeError("OpenAI Responses API returned no structured text output.")

    @staticmethod
    def estimate_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    @staticmethod
    def _build_response_meta(
        *,
        payload: dict[str, Any],
        parsed: dict[str, Any],
    ) -> dict[str, Any]:
        usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {}
        input_details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
        return {
            "response_id": parsed.get("id"),
            "model": parsed.get("model"),
            "status": parsed.get("status"),
            "prompt_cache_key": payload.get("prompt_cache_key"),
            "prompt_cache_retention": payload.get("prompt_cache_retention"),
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "cached_tokens": input_details.get("cached_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        }
