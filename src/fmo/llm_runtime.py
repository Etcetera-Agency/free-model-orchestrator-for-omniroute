import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


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
    prompt_path: Path


def assemble_prompt(site: LlmSiteConfig, context: Mapping[str, object]) -> str:
    template = site.prompt_path.read_text(encoding="utf-8")
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


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _looks_secret_key(key: str) -> bool:
    normalized = key.upper()
    return any(marker in normalized for marker in ("API_KEY", "TOKEN", "SECRET", "COOKIE", "DATABASE_URL"))
