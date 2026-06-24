from __future__ import annotations

import argparse
import json

import pytest

from fmo.cli import EXIT_CODES, run_cli
from fmo.omniroute import OmniRouteRequestError
from fmo.provider_sweep import ProviderSweepResult, format_provider_sweep_result, sweep_provider_models
from tests._composition_support import Database, MigrationRunner, Path, Repository, seed_endpoint


class SweepClient:
    def __init__(self, statuses: dict[str, int] | None = None):
        self.statuses = statuses or {}
        self.calls = []

    def post(self, path, payload, headers=None, idempotency_key=None):
        self.calls.append((path, payload, headers, idempotency_key))
        status = self.statuses.get(payload["model"], 200)
        if status >= 400:
            raise OmniRouteRequestError("POST", path, status)
        return {"status_code": status, "content": "ok"}


@pytest.mark.spec("probe-runner::Operator sweep probes provider catalog explicitly")
def test_provider_sweep_probes_provider_endpoints_and_updates_status(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    first = seed_endpoint(repository, model_id="nvidia/works", provider_id="nvidia", connection_id="nvidia-a")
    second = seed_endpoint(repository, model_id="nvidia/fails", provider_id="nvidia", connection_id="nvidia-b")
    seed_endpoint(repository, model_id="other/works", provider_id="other", connection_id="other-a")
    client = SweepClient({"nvidia/fails": 404})

    result = sweep_provider_models(repository, client, provider="nvidia", force=True)

    with repository.database.transaction() as transaction:
        statuses = transaction.execute(
            """
            SELECT provider_model_id, probe_status
            FROM provider_endpoints
            ORDER BY provider_model_id
            """
        ).fetchall()
        probes = transaction.execute(
            """
            SELECT endpoint_id, suite_version, probe_type, passed, http_status, details
            FROM endpoint_probes
            ORDER BY started_at
            """
        ).fetchall()
    assert result.changed is True
    assert result.scanned == 2
    assert result.probed == 2
    assert result.passed == 1
    assert result.failed == 1
    assert [(row["provider_model_id"], row["probe_status"]) for row in statuses] == [
        ("nvidia/fails", "failed"),
        ("nvidia/works", "passed"),
        ("other/works", "not_run"),
    ]
    assert {probe["endpoint_id"] for probe in probes} == {first["id"], second["id"]}
    assert {probe["suite_version"] for probe in probes} == {"provider-sweep-v1-stream"}
    assert {probe["probe_type"] for probe in probes} == {"provider_sweep"}
    assert [call[1]["stream"] for call in client.calls] == [True, True]
    assert [call[2] for call in client.calls] == [{"X-OmniRoute-No-Cache": "true"}] * 2


@pytest.mark.spec("probe-runner::Operator sweep probes provider catalog explicitly")
def test_provider_sweep_dry_run_lists_without_writing(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    repository = Repository(Database(postgres_url))
    seed_endpoint(repository, model_id="nvidia/works", provider_id="nvidia", connection_id="nvidia-a")
    client = SweepClient()

    result = sweep_provider_models(repository, client, provider="nvidia", dry_run=True)

    with repository.database.transaction() as transaction:
        probe_total = transaction.execute("SELECT count(*) AS total FROM endpoint_probes").fetchone()["total"]
        endpoint = transaction.execute("SELECT probe_status FROM provider_endpoints").fetchone()
    assert result.changed is False
    assert result.probed == 0
    assert result.skipped == 1
    assert result.items[0].status == "would_probe"
    assert client.calls == []
    assert probe_total == 0
    assert endpoint["probe_status"] == "not_run"


@pytest.mark.spec("cli-and-operations::Sweep provider models")
def test_sweep_provider_models_cli_routes_to_sweeper_and_formats_json():
    def sweeper(args: argparse.Namespace) -> ProviderSweepResult:
        assert args.provider == "nvidia"
        assert args.limit == 2
        assert args.offset == 4
        assert args.delay_seconds == 1.5
        assert args.force is True
        assert args.dry_run is True
        return ProviderSweepResult(
            provider=args.provider,
            dry_run=args.dry_run,
            scanned=1,
            probed=0,
            passed=0,
            failed=0,
            skipped=1,
        )

    result = run_cli(
        [
            "sweep-provider-models",
            "--provider",
            "nvidia",
            "--limit",
            "2",
            "--offset",
            "4",
            "--delay-seconds",
            "1.5",
            "--force",
            "--dry-run",
            "--json",
        ],
        preconditions_ok=True,
        provider_sweeper=sweeper,
    )

    assert result.exit_code == EXIT_CODES["success"]
    assert result.changed is False
    assert json.loads(result.output or "{}")["provider"] == "nvidia"


@pytest.mark.spec("cli-and-operations::Sweep provider models")
def test_sweep_provider_models_cli_requires_provider():
    result = run_cli(["sweep-provider-models"], preconditions_ok=True, provider_sweeper=lambda _args: None)

    assert result.exit_code == EXIT_CODES["validation_failed"]
    assert result.error_reason == "provider_required"


def test_provider_sweep_text_report_lists_per_model_status():
    result = ProviderSweepResult(provider="nvidia", dry_run=False, scanned=0, probed=0, passed=0, failed=0, skipped=0)

    assert format_provider_sweep_result(result).startswith("provider=nvidia dry_run=False")
