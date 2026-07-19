"""Unified chat-completion LLM provider abstraction.

Every specialist agent that wants LLM help (document classification, field
extraction, finding narration, report synthesis) goes through this module
instead of calling a provider SDK directly. This keeps the integration
swappable, keeps API keys out of agent code, and gives every call site the
same fallback contract: if no provider is configured, or the provider fails
or returns something that doesn't validate, ``complete_json`` returns
``None`` and the caller MUST fall back to its deterministic path. LLM output
is therefore always optional sugar, never a required dependency — the
pipeline must produce a correct (if less polished) result with
``LLM_PROVIDER=mock`` and no API key at all.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMProvider(Protocol):
    """Structured-output chat completion port used by every agent."""

    #: Human-readable label surfaced in the API/UI so the underwriter always
    #: knows whether a case ran with live LLM assistance or in mock/rule-based
    #: fallback mode (required by the "không giả vờ tích hợp" instruction).
    mode_label: str

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[ModelT],
        max_tokens: int = 800,
    ) -> ModelT | None: ...


def _strip_code_fence(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    return match.group(1) if match else text


def _extract_json_object(text: str) -> str:
    """Best-effort: take the outermost {...} block from a possibly noisy reply."""

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]


class MockLLMProvider:
    """No-network provider. Always returns ``None`` so callers use their
    deterministic fallback. Used automatically when no API key is configured,
    and explicitly in tests so LLM-touching code stays fast and reproducible
    (per docs/PROJECT-RULES.md §10: workflow tests must pass without a live LLM).
    """

    mode_label = "MOCK (rule-based fallback, no LLM configured)"

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[ModelT],
        max_tokens: int = 800,
    ) -> ModelT | None:
        return None


class _OpenAICompatibleProvider:
    """Shared implementation for any OpenAI-Chat-Completions-compatible API.

    FPT AI Marketplace, OpenAI itself, and several other providers all speak
    this same wire format, so one implementation covers them; only
    base_url/api_key/model differ.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        mode_label: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(1, max_retries)
        self.mode_label = mode_label

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[ModelT],
        max_tokens: int = 800,
    ) -> ModelT | None:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        f"{self._base_url}/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                response.raise_for_status()
                body = response.json()
                message = body["choices"][0]["message"]
                # Some reasoning-tuned models on the FPT marketplace (e.g.
                # DeepSeek-V4-Flash) put the final answer in
                # reasoning_content and leave content null. Try both.
                raw = message.get("content") or message.get("reasoning_content") or ""
                candidate = _extract_json_object(_strip_code_fence(raw))
                data = json.loads(candidate)
                return schema.model_validate(data)
            except (httpx.HTTPError, json.JSONDecodeError, ValidationError, KeyError, IndexError) as exc:
                last_error = exc
                logger.warning(
                    "LLM call failed (attempt %s/%s, provider=%s): %s",
                    attempt,
                    self._max_retries,
                    self.mode_label,
                    exc,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(0.2 * attempt)
        logger.warning(
            "LLM call exhausted retries (provider=%s): %s — falling back to deterministic path.",
            self.mode_label,
            last_error,
        )
        return None


class FPTLLMProvider(_OpenAICompatibleProvider):
    """FPT AI Marketplace — the LLM provider issued for this competition.

    Reuses the FPT_API_KEY/FPT_BASE_URL already configured for embeddings;
    the marketplace serves both chat and embedding models behind one key.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.fpt_api_key.strip():
            raise RuntimeError("FPT_API_KEY is required when LLM_PROVIDER=fpt.")
        super().__init__(
            base_url=settings.fpt_base_url,
            api_key=settings.fpt_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_request_timeout_seconds,
            max_retries=settings.llm_max_retries,
            mode_label=f"FPT:{settings.llm_model} (live)",
        )


class OpenAIProvider(_OpenAICompatibleProvider):
    """Optional provider for teams that want to swap in an OpenAI key."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        super().__init__(
            base_url="https://api.openai.com",
            api_key=settings.openai_api_key,
            model=settings.llm_model or "gpt-4o-mini",
            timeout_seconds=settings.llm_request_timeout_seconds,
            max_retries=settings.llm_max_retries,
            mode_label=f"OpenAI:{settings.llm_model or 'gpt-4o-mini'} (live)",
        )


class AnthropicProvider:
    """Optional provider for teams that want to swap in an Anthropic key.

    Not the default for this competition build (FPT is), kept for provider
    parity per the requested LLMProvider/AnthropicProvider/OpenAIProvider/
    MockProvider shape. Uses the Messages API shape, which differs from the
    OpenAI-compatible providers above, so it is not a subclass of
    ``_OpenAICompatibleProvider``.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key.strip():
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic.")
        self._api_key = settings.anthropic_api_key
        self._model = settings.llm_model or "claude-sonnet-5"
        self._timeout_seconds = settings.llm_request_timeout_seconds
        self._max_retries = max(1, settings.llm_max_retries)
        self.mode_label = f"Anthropic:{self._model} (live)"

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: type[ModelT],
        max_tokens: int = 800,
    ) -> ModelT | None:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": self._api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": self._model,
                            "max_tokens": max_tokens,
                            "system": system,
                            "messages": [{"role": "user", "content": user}],
                        },
                    )
                response.raise_for_status()
                body = response.json()
                raw = "".join(
                    block.get("text", "") for block in body.get("content", [])
                )
                candidate = _extract_json_object(_strip_code_fence(raw))
                data = json.loads(candidate)
                return schema.model_validate(data)
            except (httpx.HTTPError, json.JSONDecodeError, ValidationError, KeyError, IndexError) as exc:
                last_error = exc
                logger.warning("Anthropic call failed (attempt %s/%s): %s", attempt, self._max_retries, exc)
                if attempt < self._max_retries:
                    await asyncio.sleep(0.2 * attempt)
        logger.warning("Anthropic call exhausted retries: %s — falling back.", last_error)
        return None


def build_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Factory used by runtime wiring. Never raises: falls back to Mock."""

    settings = settings or get_settings()
    provider = settings.llm_provider.strip().lower()
    try:
        if provider == "fpt":
            return FPTLLMProvider(settings)
        if provider == "openai":
            return OpenAIProvider(settings)
        if provider == "anthropic":
            return AnthropicProvider(settings)
        if provider == "mock":
            return MockLLMProvider()
    except RuntimeError as exc:
        logger.warning("%s — falling back to mock/rule-based mode.", exc)
        return MockLLMProvider()
    logger.warning("Unknown LLM_PROVIDER=%r — falling back to mock/rule-based mode.", provider)
    return MockLLMProvider()
