import os
from pathlib import Path

import pytest

from fmo.apply_guard import ApplyPreconditions, check_apply_preconditions
from fmo.config import StartupConfig, validate_startup
from fmo.db import MigrationRunner
from fmo.idempotency import stable_hash
from fmo.llm_runtime import LlmSiteConfig, assemble_prompt, redact_secrets
from fmo.omniroute import OmniRouteClient, OmniRouteVersionGate
from fmo.state import ComboState, EndpointState, transition_combo, transition_endpoint


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "json": json,
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_schema_sql_applies_on_real_postgres(postgres_url):
    runner = MigrationRunner(postgres_url)
    runner.apply_schema(Path("reference/db/schema.sql"))
    tables = runner.table_names()
    assert "provider_endpoints" in tables
    assert "sync_runs" in tables
    assert "quota_attribution_groups" in tables


def test_omniroute_client_auth_request_id_and_retry_after():
    transport = FakeTransport(
        [
            FakeResponse(429, {"error": "slow"}, {"Retry-After": "0"}),
            FakeResponse(200, {"ok": True}),
        ]
    )
    client = OmniRouteClient(
        base_url="https://omniroute.test",
        api_key="secret",
        transport=transport,
        sleep=lambda _: None,
    )

    result = client.get("/api/providers")

    assert result == {"ok": True}
    assert len(transport.requests) == 2
    first = transport.requests[0]
    assert first["headers"]["Authorization"] == "Bearer secret"
    assert first["headers"]["X-Request-Id"]


def test_omniroute_client_does_not_retry_post_apply():
    transport = FakeTransport([FakeResponse(429, {"error": "slow"}, {"Retry-After": "1"})])
    client = OmniRouteClient(base_url="https://omniroute.test", transport=transport)

    with pytest.raises(RuntimeError, match="429"):
        client.post("/api/combos/fmo-role", {"models": []})

    assert len(transport.requests) == 1


def test_unknown_omniroute_version_read_only_forbids_apply():
    known = OmniRouteVersionGate({"1.4.0"})
    assert known.evaluate("1.4.0").can_apply is True
    unknown = known.evaluate("9.9.9")
    assert unknown.can_read is True
    assert unknown.can_apply is False


def test_startup_validation_fails_before_model_endpoint_call(monkeypatch):
    calls = []

    def health_check():
        calls.append("health")
        return {"version": "1.4.0"}

    def model_check():
        calls.append("model")

    monkeypatch.delenv("DATABASE_URL", raising=False)
    cfg = StartupConfig(
        omniroute_url="http://127.0.0.1:20128",
        database_url=None,
        hermes_inventory_mode="filesystem",
        hermes_home="/tmp/hermes",
        hermes_agents_path="/tmp/hermes/agents",
        hermes_routines_path="/tmp/hermes/routines",
        hermes_inventory_cron="bad cron",
    )

    with pytest.raises(ValueError):
        validate_startup(cfg, health_check=health_check, model_endpoint_check=model_check)

    assert calls == []


@pytest.mark.parametrize(
    ("state", "target"),
    [
        (EndpointState.EXCLUDED_UNKNOWN, EndpointState.ACTIVE),
        (EndpointState.QUOTA_EXHAUSTED, EndpointState.ACTIVE),
        (EndpointState.PROBE_FAILED, EndpointState.ACTIVE),
    ],
)
def test_forbidden_endpoint_transitions_rejected(state, target):
    with pytest.raises(ValueError):
        transition_endpoint(state, target)


def test_planned_combo_cannot_apply_without_snapshot():
    with pytest.raises(ValueError):
        transition_combo(ComboState.PLANNED, ComboState.APPLIED)


def test_apply_refused_when_any_precondition_fails():
    preconditions = ApplyPreconditions(
        db_available=True,
        snapshot_saved=True,
        desired_state_valid=True,
        quota_safe=False,
        probes_passed=True,
    )

    with pytest.raises(ValueError, match="quota_safe"):
        check_apply_preconditions(preconditions)


def test_stable_hash_makes_unchanged_inputs_skip_changes():
    left = stable_hash({"models": ["b", "a"], "role": "coder"})
    right = stable_hash({"role": "coder", "models": ["b", "a"]})
    changed = stable_hash({"role": "coder", "models": ["a", "b"]})

    assert left == right
    assert left != changed


def test_llm_prompt_loads_external_file_and_redacts_secrets(tmp_path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Use endpoint {{ endpoint_id }} with {{ OMNIROUTE_API_KEY }}", encoding="utf-8")
    site = LlmSiteConfig(name="quota-research", model="free-model", prompt_path=prompt_file)
    prompt = assemble_prompt(site, {"endpoint_id": "provider-account-1", "OMNIROUTE_API_KEY": "secret"})

    assert "provider-account-1" in prompt
    assert "secret" not in prompt
    assert "OMNIROUTE_API_KEY" not in prompt


def test_redact_secrets_removes_database_credentials_and_tokens():
    text = "postgresql://user:pass@db:5432/app Bearer abc123 cookie=session"
    redacted = redact_secrets(text)

    assert "pass" not in redacted
    assert "abc123" not in redacted
    assert "session" not in redacted
