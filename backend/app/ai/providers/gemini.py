"""
VoltAI Gemini LLM Provider Adapter (Stage 10)

Implements BaseLLMProvider using the Google Gemini REST API.
Does NOT log or expose API keys in error tracebacks or exception messages.
Supports dependency injection of httpx.Client for unit testing without live network calls.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from backend.app.ai.providers import (
    BaseLLMProvider,
    LLMAuthError,
    LLMProviderError,
    LLMQuotaError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini provider adapter.
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gemini-1.5-flash",
        timeout_seconds: float = 15.0,
        max_retries: int = 1,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._api_key = api_key
        self._model = model_name
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._client = http_client

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def generate_explanation(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a grounded request to Gemini REST API and return the response text.
        """
        if not self._api_key:
            raise LLMAuthError("Gemini API key is not configured.")

        url = f"{GEMINI_BASE_URL}/models/{self._model}:generateContent"
        params = {"key": self._api_key}

        payload: Dict[str, Any] = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        # Safe logging without exposing key
        logger.info("Executing Gemini LLM request (model=%s)", self._model)

        raw = self._do_post_with_retry(url, params, payload)
        return self._parse_gemini_response(raw)

    def _do_post_with_retry(
        self, url: str, params: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                return self._do_post(url, params, payload)
            except LLMTimeoutError as exc:
                last_exc = exc
                logger.warning("Gemini API timeout attempt %d/%d", attempt + 1, self._max_retries + 1)
            except (LLMAuthError, LLMQuotaError):
                # Non-retriable auth/quota errors
                raise

        raise LLMTimeoutError(f"Gemini API timed out after {self._max_retries + 1} attempt(s).") from last_exc

    def _do_post(
        self, url: str, params: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if self._client is not None:
            return self._execute_request(self._client, url, params, payload)
        else:
            with httpx.Client(timeout=self._timeout) as client:
                return self._execute_request(client, url, params, payload)

    def _execute_request(
        self, client: httpx.Client, url: str, params: Dict[str, Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            response = client.post(url, params=params, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Connection to Gemini API timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"Network error communicating with Gemini API: {exc}") from exc

        if response.status_code in (401, 403):
            raise LLMAuthError(f"Gemini authentication failed (HTTP {response.status_code}).")
        elif response.status_code == 429:
            raise LLMQuotaError("Gemini rate limit or quota exceeded (HTTP 429).")
        elif response.status_code >= 500:
            raise LLMProviderError(f"Gemini server error (HTTP {response.status_code}).")
        elif response.status_code != 200:
            raise LLMProviderError(f"Gemini returned unexpected HTTP {response.status_code}.")

        try:
            return response.json()
        except Exception as exc:
            raise LLMProviderError(f"Failed to parse Gemini response JSON: {exc}") from exc

    def _parse_gemini_response(self, raw: Dict[str, Any]) -> str:
        try:
            candidates = raw.get("candidates", [])
            if not candidates:
                raise LLMProviderError("Gemini response contains no candidates.")

            first_cand = candidates[0]
            content = first_cand.get("content", {})
            parts = content.get("parts", [])

            if not parts:
                finish_reason = first_cand.get("finishReason", "UNKNOWN")
                raise LLMProviderError(f"Gemini returned no text content (finishReason={finish_reason}).")

            text_parts = [p.get("text", "") for p in parts if "text" in p]
            result_text = "".join(text_parts).strip()

            if not result_text:
                raise LLMProviderError("Gemini returned empty text response.")

            return result_text
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"Malformed Gemini API response payload: {exc}") from exc
