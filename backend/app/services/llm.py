"""FPT-only LLM provider with bounded retries and validated structured output."""

from __future__ import annotations

import asyncio
import json
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings


OutputT = TypeVar("OutputT", bound=BaseModel)


class LLMProviderError(RuntimeError):
    """A safe provider error that never includes credentials or raw documents."""


class LLMProvider:
    provider_name = "unavailable"
    model_name = ""
    available = False

    async def generate_structured(
        self,
        output_model: type[OutputT],
        *,
        system_prompt: str,
        user_prompt: str,
        operation: str,
    ) -> OutputT:
        raise LLMProviderError("FPT LLM is not configured.")


class FPTLLMProvider(LLMProvider):
    """Call the official FPT AI Marketplace chat-completions endpoint."""

    provider_name = "fpt"
    available = True

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str = "https://mkp-api.fptcloud.com",
        timeout_seconds: float = 60.0,
        max_attempts: int = 2,
        temperature: float = 0.1,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("FPT_API_KEY is required for FPT LLM mode.")
        if not model_name.strip():
            raise ValueError("LLM_MODEL is required for FPT LLM mode.")
        if max_attempts < 1:
            raise ValueError("LLM_MAX_ATTEMPTS must be at least 1.")
        self.api_key = api_key
        self.model_name = model_name
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.temperature = temperature
        self._client = client

    async def generate_structured(
        self,
        output_model: type[OutputT],
        *,
        system_prompt: str,
        user_prompt: str,
        operation: str,
    ) -> OutputT:
        schema = output_model.model_json_schema()
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                payload = await self._request(
                    system_prompt=(
                        f"{system_prompt}\nReturn only one valid JSON object matching this "
                        f"JSON Schema: {json.dumps(schema, ensure_ascii=False)}"
                    ),
                    user_prompt=user_prompt,
                )
                return output_model.model_validate_json(self._json_text(payload))
            except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    await asyncio.sleep(0.25 * attempt)
        raise LLMProviderError(
            f"FPT LLM operation {operation!r} failed after {self.max_attempts} attempts."
        ) from last_error

    async def _request(self, *, system_prompt: str, user_prompt: str) -> dict[str, object]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.temperature,
                    "stream": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("FPT response must be a JSON object.")
            return payload
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _json_text(payload: dict[str, object]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("FPT response has no choices.")
        first = choices[0]
        if not isinstance(first, dict):
            raise ValueError("FPT response choice is invalid.")
        message = first.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ValueError("FPT response has no message content.")
        content = message["content"].strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        return fenced.group(1) if fenced else content


def build_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Return FPT live mode only when both the competition key and model are set."""

    config = settings or get_settings()
    if config.llm_provider.lower() != "fpt":
        return LLMProvider()
    if not config.fpt_api_key.strip() or not config.llm_model.strip():
        return LLMProvider()
    return FPTLLMProvider(
        api_key=config.fpt_api_key,
        model_name=config.llm_model,
        base_url=config.fpt_base_url,
        timeout_seconds=config.fpt_request_timeout_seconds,
        max_attempts=config.llm_max_attempts,
        temperature=config.llm_temperature,
    )
