from __future__ import annotations

import json
from typing import Generic, Protocol, TypeVar

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings


StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class LLMGenerationError(RuntimeError):
    pass


class StructuredLLM(Protocol):
    def invoke_structured(
        self,
        *,
        schema: type[StructuredOutput],
        system_prompt: str,
        user_prompt: str,
    ) -> StructuredOutput: ...


class OpenAICompatibleStructuredLLM:
    """Provider-neutral JSON contract over an OpenAI-compatible chat endpoint."""

    def __init__(self, settings: Settings | None = None) -> None:
        current = settings or get_settings()
        if current.llm_provider != "openai_compatible":
            raise ValueError("LLM_PROVIDER must be openai_compatible")
        if current.llm_api_key is None or not current.llm_api_key.get_secret_value():
            raise ValueError("LLM_API_KEY is required for real agent execution")
        self._model = ChatOpenAI(
            model=current.llm_model,
            api_key=current.llm_api_key,
            base_url=current.llm_api_base,
            temperature=current.llm_temperature,
            max_tokens=current.llm_max_tokens,
            max_retries=2,
            timeout=90,
        )

    def invoke_structured(
        self,
        *,
        schema: type[StructuredOutput],
        system_prompt: str,
        user_prompt: str,
    ) -> StructuredOutput:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        contract_prompt = (
            f"{system_prompt}\n\n"
            "Return exactly one valid JSON object. Do not use Markdown fences. "
            "Do not reveal hidden chain-of-thought; provide only concise structured "
            "rationale fields requested by the schema. Never invent missing values, "
            "document IDs, policy citations, or calculations.\n\n"
            f"JSON Schema:\n{schema_json}"
        )
        messages = [
            SystemMessage(content=contract_prompt),
            HumanMessage(content=user_prompt),
        ]
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._model.invoke(messages)
            except Exception as exc:
                raise LLMGenerationError("LLM provider request failed") from exc

            content = response.content
            if not isinstance(content, str):
                last_error = ValueError("LLM returned a non-text response")
                content = ""
            else:
                try:
                    payload = self._extract_json_object(content)
                    return schema.model_validate(payload)
                except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                    last_error = exc

            if attempt < 2:
                feedback = self._validation_feedback(last_error)
                messages.extend(
                    [
                        AIMessage(content=content[:8_000]),
                        HumanMessage(
                            content=(
                                "Your JSON failed contract validation. Correct only the "
                                "reported structural/value errors and return the complete "
                                "JSON object again. Do not invent evidence.\n\n"
                                f"Validation feedback:\n{feedback}"
                            )
                        ),
                    ]
                )
        raise LLMGenerationError(
            "LLM response did not satisfy the structured output contract"
        ) from last_error

    @staticmethod
    def _validation_feedback(error: Exception | None) -> str:
        if isinstance(error, ValidationError):
            compact = [
                {
                    "path": ".".join(str(item) for item in issue["loc"]),
                    "message": issue["msg"],
                }
                for issue in error.errors(include_url=False, include_input=False)[:12]
            ]
            return json.dumps(compact, ensure_ascii=False)
        return str(error or "Response was not valid JSON")[:2_000]

    @staticmethod
    def _extract_json_object(content: str) -> object:
        normalized = content.strip()
        if normalized.startswith("```"):
            normalized = normalized.removeprefix("```json").removeprefix("```")
            normalized = normalized.removesuffix("```").strip()
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            start = normalized.find("{")
            end = normalized.rfind("}")
            if start < 0 or end <= start:
                raise
            return json.loads(normalized[start : end + 1])


class StaticStructuredLLM(Generic[StructuredOutput]):
    """Explicit test double; never selected by runtime configuration."""

    def __init__(self, response: StructuredOutput) -> None:
        self._response = response

    def invoke_structured(
        self,
        *,
        schema: type[StructuredOutput],
        system_prompt: str,
        user_prompt: str,
    ) -> StructuredOutput:
        del system_prompt, user_prompt
        return schema.model_validate(self._response.model_dump())
