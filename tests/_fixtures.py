"""Loaders for recorded external-source responses.

Recordings live in ``reference/fixtures/external-responses`` and preserve the
real response shapes (with secrets/PII redacted). Tests replay them through the
production parsers so payload shape and schema drift are exercised against real
data, not hand-fabricated dicts.
"""

import json
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "reference" / "fixtures"
FIXTURE_DIR = FIXTURE_ROOT / "external-responses"
HERMES_FIXTURE_DIR = FIXTURE_ROOT / "hermes"


def hermes_fixture_path(name: str) -> Path:
    """Absolute path to a recorded Hermes fixture file."""
    return HERMES_FIXTURE_DIR / name


def load_hermes_fixture(name: str) -> Any:
    """Parsed JSON for a recorded Hermes source fixture (e.g. cron_jobs.json)."""
    return json.loads(hermes_fixture_path(name).read_text())


def load_fixture(name: str) -> dict[str, Any]:
    """Return the full recorded envelope for ``name`` (with or without .json)."""
    if not name.endswith(".json"):
        name = f"{name}.json"
    return json.loads((FIXTURE_DIR / name).read_text())


def fixture_body(name: str) -> Any:
    """Return just the recorded response body.

    OmniRoute / models.dev recordings store the parsed JSON under ``body``;
    Artificial Analysis recordings nest it under ``response.body``.
    """
    envelope = load_fixture(name)
    if "body" in envelope:
        return envelope["body"]
    return envelope["response"]["body"]
