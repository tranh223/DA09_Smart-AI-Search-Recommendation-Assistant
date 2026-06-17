import json
import os
import time
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
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/responses")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
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
