from pathlib import Path

import pytest

from fmo.db import MigrationRunner
from fmo.persistence import Database, Repository
from fmo.pipeline import (
    EXIT_CODES,
    PipelineRunner,
    Stage,
    StageResult,
    outcome_exit_code,
)
from tests._stage_effects import assert_success_has_declared_effect


@pytest.fixture()
def repository(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    return Repository(Database(postgres_url))


@pytest.mark.spec("pipeline-orchestration::Run is identified")
def test_starting_run_persists_run_record(repository):
    runner = PipelineRunner(repository, stages=[])

    result = runner.run(trigger="manual")

    with repository.database.transaction() as transaction:
        run = repository.runs.get(transaction, result.run_id)
    assert run is not None
    assert run["run_type"] == "full"
    assert run["trigger"] == "manual"
    assert run["status"] == "success"


@pytest.mark.spec("pipeline-orchestration::Run is identified")
@pytest.mark.spec("pipeline-orchestration::Stages run in order")
@pytest.mark.spec("scheduler::External metadata before discovery and scoring")
@pytest.mark.spec("telemetry-sync::Daily sync before scoring")
@pytest.mark.spec("persistence::Stages do not embed schema SQL")
def test_stages_execute_in_order_and_record_status(repository):
    calls = []

    def first(context):
        calls.append(("metadata", context.run_id))
        return StageResult(status="success", idempotency_key="metadata-v1")

    def second(context):
        calls.append(("discovery", context.run_id))
        return StageResult(status="success", idempotency_key="discovery-v1")

    runner = PipelineRunner(
        repository,
        stages=[
            Stage("metadata", first, idempotency_key="metadata-v1"),
            Stage("discovery", second, idempotency_key="discovery-v1"),
        ],
    )

    result = runner.run(trigger="manual")

    assert [name for name, _run_id in calls] == ["metadata", "discovery"]
    assert all(run_id == result.run_id for _name, run_id in calls)
    with repository.database.transaction() as transaction:
        run = repository.runs.get(transaction, result.run_id)
    assert [stage["name"] for stage in run["error_json"]["stages"]] == ["metadata", "discovery"]
    assert [stage["status"] for stage in run["error_json"]["stages"]] == ["success", "success"]


@pytest.mark.spec("pipeline-orchestration::Unchanged re-run skips work")
def test_unchanged_stage_idempotency_key_skips_reexecution(repository):
    calls = []

    def stage_fn(context):
        calls.append(context.run_id)
        return StageResult(status="success", idempotency_key="same-input")

    runner = PipelineRunner(repository, stages=[Stage("probe", stage_fn, idempotency_key="same-input")])

    first = runner.run(trigger="manual")
    second = runner.run(trigger="manual")

    assert calls == [first.run_id]
    assert second.skipped_stages == ["probe"]
    with repository.database.transaction() as transaction:
        run = repository.runs.get(transaction, second.run_id)
    assert run["error_json"]["stages"][0]["skipped"] is True


@pytest.mark.spec("pipeline-orchestration::Failed gate stops apply")
def test_failed_safety_gate_stops_downstream_apply(repository):
    calls = []

    def quota_gate(context):
        calls.append("quota")
        return StageResult(status="unsafe_to_apply", idempotency_key="quota-v1", reason="quota")

    def apply_stage(context):
        calls.append("apply")
        return StageResult(status="success", idempotency_key="apply-v1", changed=True)

    runner = PipelineRunner(
        repository,
        stages=[
            Stage("quota", quota_gate),
            Stage("apply", apply_stage),
        ],
    )

    result = runner.run(trigger="manual")

    assert calls == ["quota"]
    assert result.exit_code == 5
    assert result.changed is False
    assert result.status == "unsafe_to_apply"


@pytest.mark.spec("pipeline-orchestration::Partial data not consumed")
@pytest.mark.spec("pipeline-orchestration::Stale stage does not abort the run")
@pytest.mark.spec("pipeline-orchestration::Stale stage yields exit 2 while later stages run")
def test_partial_stale_output_does_not_abort_dependent_stages(repository):
    calls = []

    def discovery(context):
        calls.append("discovery")
        return StageResult(status="partial_stale", idempotency_key="discovery-v1")

    def matcher(context):
        calls.append("matcher")
        return StageResult(status="success", idempotency_key="matcher-v1")

    result = PipelineRunner(
        repository,
        stages=[
            Stage("discovery", discovery, idempotency_key="discovery-v1"),
            Stage("matcher", matcher, idempotency_key="matcher-v1"),
        ],
    ).run(trigger="manual")

    assert calls == ["discovery", "matcher"]
    assert result.exit_code == 2
    assert result.status == "partial_stale"


@pytest.mark.spec("pipeline-orchestration::No combo test call")
def test_runner_never_calls_combo_test(repository):
    class Client:
        def __init__(self):
            self.paths = []

        def post(self, path, payload):
            self.paths.append(path)
            if path == "/api/combos/test":
                raise AssertionError("combo test must not be called")
            return {"ok": True}

    client = Client()

    def apply_stage(context):
        client.post("/api/combos/fmo-role", {"models": []})
        return StageResult(status="success", idempotency_key="apply-v1", changed=True)

    PipelineRunner(repository, stages=[Stage("apply", apply_stage)]).run(trigger="manual")

    assert client.paths == ["/api/combos/fmo-role"]


@pytest.mark.parametrize(
    ("status", "exit_code"),
    [
        ("success", 0),
        ("partial_stale", 2),
        ("validation_failed", 3),
        ("not_implemented", 3),
        ("external_dependency_failed", 4),
        ("unsafe_to_apply", 5),
        ("apply_failed_rolled_back", 6),
        ("rollback_failed", 7),
    ],
)
@pytest.mark.spec("pipeline-orchestration::Unsafe apply outcome")
@pytest.mark.spec("pipeline-orchestration::External dependency failure outcome")
def test_outcomes_map_to_exit_codes(status, exit_code):
    assert outcome_exit_code(status) == exit_code
    assert EXIT_CODES[status] == exit_code


@pytest.mark.spec("pipeline-orchestration::Unsafe apply outcome")
def test_unsafe_apply_outcome_maps_to_code_5(repository):
    runner = PipelineRunner(
        repository,
        stages=[Stage("apply", lambda context: StageResult(status="unsafe_to_apply", idempotency_key="apply-v1"))],
    )

    result = runner.run(trigger="manual")

    assert result.exit_code == 5
    assert result.changed is False


@pytest.mark.spec("pipeline-orchestration::External dependency failure outcome")
@pytest.mark.spec("scheduler::Metadata sync failure is conservative")
def test_external_dependency_failure_maps_to_code_4(repository):
    runner = PipelineRunner(
        repository,
        stages=[
            Stage(
                "metadata",
                lambda context: StageResult(status="external_dependency_failed", idempotency_key="metadata-v1"),
            )
        ],
    )

    result = runner.run(trigger="manual")

    assert result.exit_code == 4


@pytest.mark.spec("pipeline-orchestration::Stage success requires a real effect")
def test_success_stage_without_declared_effect_fails_effect_harness(repository):
    runner = PipelineRunner(
        repository,
        stages=[Stage("model-matching", lambda context: StageResult(status="success", idempotency_key="fake"))],
    )

    result = runner.run(trigger="manual")

    with pytest.raises(AssertionError):
        assert_success_has_declared_effect(result.stage_results[0])
