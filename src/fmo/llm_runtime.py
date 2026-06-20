import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, TypeVar

from pydantic import BaseModel, ValidationError


SECRET_PATTERNS = (
    re.compile(r"postgresql://[^:\s]+:[^@\s]+@"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"cookie=[^\s]+", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|COOKIE)[A-Z0-9_]*\b\s*[:=]\s*[^\s]+"),
)


@dataclass(frozen=True)
class LlmSiteConfig:
    name: str
    model: str
    prompt_path: Path | None = None
    max_prompt_chars: int = 8000
    retries: int = 1
    advisory: bool = False


@dataclass(frozen=True)
class LlmProviderConfig:
    base_url: str
    api_key: str
    model: str
    structured_output_mode: str = "json_schema"


class LlmRuntimeError(Exception):
    pass


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class SharedInstructorRuntime:
    def __init__(self, *, provider: LlmProviderConfig, transport):
        self.provider = provider
        self.transport = transport

    def complete(
        self,
        *,
        site: LlmSiteConfig,
        context: Mapping[str, object],
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        prompt = limit_prompt(assemble_prompt(site, context), site.max_prompt_chars)
        last_error: Exception | None = None
        attempts = max(site.retries, 1)
        for _ in range(attempts):
            try:
                raw = self.transport(
                    {
                        "base_url": self.provider.base_url,
                        "model": site.model or self.provider.model,
                        "site": site.name,
                        "mode": self.provider.structured_output_mode,
                        "prompt": prompt,
                        "response_model": response_model,
                    }
                )
                return validate_structured_completion(response_model, raw)
            except Exception as exc:
                last_error = exc
        raise LlmRuntimeError(str(last_error)) from last_error


def complete_with_adapter(
    instructor_call,
    *,
    site: LlmSiteConfig,
    context: Mapping[str, object],
    response_model: type[ResponseModel],
) -> ResponseModel:
    runtime = SharedInstructorRuntime(
        provider=LlmProviderConfig(base_url="https://omniroute.local/v1", api_key="[REDACTED]", model=site.model),
        transport=instructor_call,
    )
    return runtime.complete(site=site, context=context, response_model=response_model)


def assemble_prompt(site: LlmSiteConfig, context: Mapping[str, object]) -> str:
    template = site.prompt_path.read_text(encoding="utf-8") if site.prompt_path else str(context.get("prompt", ""))
    safe_context = {
        key: value
        for key, value in context.items()
        if not _looks_secret_key(key)
    }
    prompt = template
    for key, value in safe_context.items():
        prompt = prompt.replace("{{ " + key + " }}", str(value))
        prompt = prompt.replace("{{" + key + "}}", str(value))
    unresolved = re.sub(r"\{\{\s*[^}]+\s*\}\}", "", prompt)
    return redact_secrets(unresolved)


def limit_prompt(prompt: str, max_chars: int) -> str:
    redacted = redact_secrets(prompt)
    if len(redacted) <= max_chars:
        return redacted
    return redacted[:max_chars]


def validate_structured_completion(response_model: type[ResponseModel], raw: Any) -> ResponseModel:
    payload = _coerce_completion_payload(raw)
    try:
        return response_model.model_validate(payload)
    except ValidationError as exc:
        raise LlmRuntimeError(str(exc)) from exc


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _looks_secret_key(key: str) -> bool:
    normalized = key.upper()
    return any(marker in normalized for marker in ("API_KEY", "TOKEN", "SECRET", "COOKIE", "DATABASE_URL"))


def _coerce_completion_payload(raw: Any) -> Any:
    if isinstance(raw, BaseModel):
        return raw
    if isinstance(raw, dict):
        content = _openai_message_content(raw)
        if content is not None:
            return _coerce_completion_payload(content)
        arguments = raw.get("arguments")
        if isinstance(arguments, str):
            return _json_from_text(arguments)
        return raw
    if isinstance(raw, str):
        return _json_from_text(raw)
    return raw


def _openai_message_content(raw: dict) -> str | None:
    choices = raw.get("choices")
    if not choices:
        return None
    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        function = tool_calls[0].get("function", {})
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            return arguments
    content = message.get("content")
    return content if isinstance(content, str) else None


def _json_from_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LlmRuntimeError("structured_completion_not_json")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LlmRuntimeError("structured_completion_not_json") from exc
