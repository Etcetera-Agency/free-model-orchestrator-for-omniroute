import os
from pathlib import Path

import pytest

from fmo.apply_guard import ApplyPreconditions, check_apply_preconditions
from fmo.config import StartupConfig, validate_startup, validate_static_config
from fmo.db import MigrationRunner
from fmo.idempotency import stable_hash
from fmo.llm_runtime import LlmSiteConfig, assemble_prompt, redact_secrets
from fmo.omniroute import OmniRouteClient, OmniRouteVersionGate, _retry_after_seconds
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


@pytest.mark.spec("data-model::Fresh install")
def test_schema_sql_applies_on_real_postgres(postgres_url):
    runner = MigrationRunner(postgres_url)
    runner.apply_schema(Path("reference/db/schema.sql"))
    tables = runner.table_names()
    assert "provider_endpoints" in tables
    assert "sync_runs" in tables
    assert "quota_attribution_groups" in tables


@pytest.mark.spec("omniroute-client::429 with Retry-After")
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


@pytest.mark.spec("omniroute-client::GET 429 retries exhausted")
def test_omniroute_client_get_429_retry_exhaustion_raises_runtime_error():
    transport = FakeTransport(
        [
            FakeResponse(429, {"error": "slow"}, {"Retry-After": "0"}),
            FakeResponse(429, {"error": "still slow"}, {"Retry-After": "0"}),
        ]
    )
    client = OmniRouteClient(
        base_url="https://omniroute.test/api",
        transport=transport,
        max_get_retries=1,
        sleep=lambda _: None,
    )

    with pytest.raises(RuntimeError, match="HTTP 429"):
        client.get("/providers")

    assert len(transport.requests) == 2


@pytest.mark.spec("omniroute-client::GET non-retriable error")
@pytest.mark.parametrize("status_code", [400, 404, 500, 503])
def test_omniroute_client_get_non_retry_errors_raise_without_retry(status_code):
    transport = FakeTransport([FakeResponse(status_code, {"error": "bad"})])
    client = OmniRouteClient(
        base_url="https://omniroute.test/api",
        transport=transport,
        max_get_retries=3,
    )

    with pytest.raises(RuntimeError, match=f"HTTP {status_code}"):
        client.get("/providers")

    assert len(transport.requests) == 1


@pytest.mark.spec("omniroute-client::Invalid Retry-After")
@pytest.mark.parametrize("value", ["", "abc", "-2", None])
def test_retry_after_invalid_empty_nonnumeric_or_negative_is_zero(value):
    assert _retry_after_seconds(value) == 0.0


@pytest.mark.spec("omniroute-client::Leading slash path")
def test_omniroute_client_leading_slash_path_stays_under_base_path():
    transport = FakeTransport([FakeResponse(200, {"ok": True})])
    client = OmniRouteClient(base_url="https://omniroute.test/api", transport=transport)

    assert client.get("/providers") == {"ok": True}

    assert transport.requests[0]["url"] == "https://omniroute.test/api/providers"


@pytest.mark.spec("omniroute-client::Unknown OmniRoute version")
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


def valid_startup_config(**overrides):
    values = {
        "omniroute_url": "https://omniroute.test",
        "database_url": "postgresql://user:pass@localhost:5432/fmo",
        "hermes_inventory_mode": "filesystem",
        "hermes_home": "/tmp/hermes",
        "hermes_agents_path": "/tmp/hermes/agents",
        "hermes_routines_path": "/tmp/hermes/routines",
        "hermes_inventory_cron": "0 4 * * *",
    }
    values.update(overrides)
    return StartupConfig(**values)


@pytest.mark.spec("environment-and-connections::Bad OmniRoute URL")
@pytest.mark.parametrize("omniroute_url", ["", "ftp://omniroute.test"])
def test_static_config_rejects_bad_omniroute_url_scheme_or_empty(omniroute_url):
    with pytest.raises(ValueError, match="OMNIROUTE_URL"):
        validate_static_config(valid_startup_config(omniroute_url=omniroute_url))


@pytest.mark.spec("environment-and-connections::Missing database URL")
def test_static_config_rejects_missing_database_url():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        validate_static_config(valid_startup_config(database_url=None))


@pytest.mark.spec("environment-and-connections::Invalid inventory mode")
def test_static_config_rejects_invalid_inventory_mode():
    with pytest.raises(ValueError, match="HERMES_INVENTORY_MODE"):
        validate_static_config(valid_startup_config(hermes_inventory_mode="invalid"))


@pytest.mark.spec("environment-and-connections::Bad inventory cron")
@pytest.mark.parametrize("cron", ["0 4 * *", "0 4  * * *", ""])
def test_static_config_rejects_bad_inventory_cron(cron):
    with pytest.raises(ValueError, match="HERMES_INVENTORY_CRON"):
        validate_static_config(valid_startup_config(hermes_inventory_cron=cron))


@pytest.mark.spec("environment-and-connections::Missing filesystem inventory path")
@pytest.mark.parametrize("missing_path", ["hermes_home", "hermes_agents_path", "hermes_routines_path"])
def test_static_config_rejects_filesystem_mode_missing_any_path(missing_path):
    with pytest.raises(ValueError, match="missing filesystem"):
        validate_static_config(valid_startup_config(**{missing_path: None}))


@pytest.mark.spec("environment-and-connections::Missing command inventory command")
def test_static_config_rejects_command_mode_missing_command():
    with pytest.raises(ValueError, match="HERMES_INVENTORY_COMMAND"):
        validate_static_config(
            valid_startup_config(
                hermes_inventory_mode="command",
                hermes_home=None,
                hermes_agents_path=None,
                hermes_routines_path=None,
            )
        )


@pytest.mark.spec("environment-and-connections::Bad HTTP inventory URL")
@pytest.mark.parametrize("inventory_url", ["", "ftp://inventory.test", "https://"])
def test_static_config_rejects_http_mode_bad_inventory_url(inventory_url):
    with pytest.raises(ValueError, match="HERMES_INVENTORY_URL"):
        validate_static_config(
            valid_startup_config(
                hermes_inventory_mode="http",
                hermes_home=None,
                hermes_agents_path=None,
                hermes_routines_path=None,
                hermes_inventory_url=inventory_url,
            )
        )


@pytest.mark.spec("environment-and-connections::Health check payload is not an object")
def test_startup_validation_rejects_non_object_health_payload():
    with pytest.raises(ValueError, match="non-object"):
        validate_startup(valid_startup_config(), health_check=lambda: ["ok"])


@pytest.mark.spec("system-architecture::Reactivate exhausted endpoint too early")
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


@pytest.mark.parametrize(
    ("state", "target"),
    [
        (ComboState.SNAPSHOT_SAVED, ComboState.COMMITTED),
        (ComboState.APPLIED, ComboState.COMMITTED),
        (ComboState.COMMITTED, ComboState.APPLIED),
        (ComboState.SMOKE_PASSED, ComboState.APPLIED),
        (ComboState.VALIDATED, ComboState.PLANNED),
    ],
)
@pytest.mark.spec("data-model::Snapshot directly committed")
@pytest.mark.spec("data-model::Applied directly committed")
@pytest.mark.spec("data-model::Backward combo transition")
def test_forbidden_combo_transitions_rejected(state, target):
    with pytest.raises(ValueError):
        transition_combo(state, target)


@pytest.mark.spec("system-architecture::Missing snapshot blocks apply")
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


@pytest.mark.spec("system-architecture::Re-run with unchanged inputs")
def test_stable_hash_makes_unchanged_inputs_skip_changes():
    left = stable_hash({"models": ["b", "a"], "role": "coder"})
    right = stable_hash({"role": "coder", "models": ["b", "a"]})
    changed = stable_hash({"role": "coder", "models": ["a", "b"]})

    assert left == right
    assert left != changed


@pytest.mark.spec("environment-and-connections::Building an LLM prompt")
def test_llm_prompt_loads_external_file_and_redacts_secrets(tmp_path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Use endpoint {{ endpoint_id }} with {{ OMNIROUTE_API_KEY }}", encoding="utf-8")
    site = LlmSiteConfig(name="quota-research", model="free-model", prompt_path=prompt_file)
    prompt = assemble_prompt(site, {"endpoint_id": "provider-account-1", "OMNIROUTE_API_KEY": "secret"})

    assert "provider-account-1" in prompt
    assert "secret" not in prompt
    assert "OMNIROUTE_API_KEY" not in prompt


@pytest.mark.spec("llm-runtime::PostgreSQL URL redaction")
def test_redact_secrets_removes_database_credentials_and_tokens():
    text = "postgresql://user:pass@db:5432/app Bearer abc123 cookie=session"
    redacted = redact_secrets(text)

    assert "pass" not in redacted
    assert "abc123" not in redacted
    assert "session" not in redacted


@pytest.mark.spec("llm-runtime::Bearer token redaction")
@pytest.mark.spec("llm-runtime::Cookie assignment redaction")
@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("postgresql://user:pass@db:5432/app", "pass"),
        ("Bearer abc.def-123", "abc.def-123"),
        ("cookie=session_id=secret", "session_id=secret"),
        ("SERVICE_API_KEY=secret", "secret"),
        ("ACCESS_TOKEN:secret", "secret"),
        ("CLIENT_SECRET=secret", "secret"),
    ],
)
def test_redact_secrets_handles_each_secret_pattern(text, secret):
    redacted = redact_secrets(text)

    assert secret not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.spec("llm-runtime::Secret-like key removal")
def test_llm_prompt_omits_secret_like_context_keys_and_database_url(tmp_path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text(
        "{{ safe }} {{ DATABASE_URL }} {{ API_KEY }} {{ TOKEN }} {{ SECRET }}",
        encoding="utf-8",
    )
    site = LlmSiteConfig(name="quota-research", model="free-model", prompt_path=prompt_file)

    prompt = assemble_prompt(
        site,
        {
            "safe": "visible",
            "DATABASE_URL": "postgresql://user:pass@db:5432/app",
            "API_KEY": "api-secret",
            "TOKEN": "token-secret",
            "SECRET": "secret-secret",
        },
    )

    assert prompt.strip() == "visible"


@pytest.mark.spec("llm-runtime::Unresolved placeholder cleanup")
def test_llm_prompt_removes_unresolved_placeholders(tmp_path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Use {{ endpoint_id }} {{ missing }}", encoding="utf-8")
    site = LlmSiteConfig(name="quota-research", model="free-model", prompt_path=prompt_file)

    prompt = assemble_prompt(site, {"endpoint_id": "e1"})

    assert prompt == "Use e1 "
    assert "{{" not in prompt
