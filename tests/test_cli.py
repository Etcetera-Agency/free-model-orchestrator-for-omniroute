import pytest

from fmo.cli import CliResult, EXIT_CODES, run_cli


class FakeRunner:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []

    def __call__(self, command, args):
        self.calls.append((command, args))
        if self.results:
            return self.results.pop(0)
        return CliResult(exit_code=0, changed=False)


@pytest.mark.spec("cli-and-operations::Stage command invokes its stage")
@pytest.mark.parametrize("command", ["scan-providers", "match-models", "probe-models", "score-roles", "allocate", "diff"])
def test_stage_commands_invoke_pipeline_runner(command):
    runner = FakeRunner()

    result = run_cli([command, "--provider", "openai"], preconditions_ok=True, pipeline_runner=runner)

    assert result.exit_code == 0
    assert runner.calls[0][0] == command
    assert runner.calls[0][1].provider == "openai"


@pytest.mark.spec("cli-and-operations::Stage command invokes its stage")
def test_stage_failure_surfaces_runner_exit_code():
    runner = FakeRunner([CliResult(exit_code=EXIT_CODES["external_dependency_failed"], changed=False)])

    result = run_cli(["allocate"], preconditions_ok=True, pipeline_runner=runner)

    assert result.exit_code == 4


@pytest.mark.spec("cli-and-operations::aa-index subcommand routes to the handler")
def test_aa_index_subcommand_invokes_handler_instead_of_default_noop():
    calls = []

    def handler(command, args):
        calls.append((command, args.aa_command))
        return CliResult(exit_code=0, changed=True)

    result = run_cli(["aa-index", "analyze"], preconditions_ok=True, aa_index_handler=handler)

    assert result.exit_code == 0
    assert result.changed is True
    assert calls == [("analyze", "analyze")]


@pytest.mark.spec("cli-and-operations::aa-index failure maps to an exit code")
def test_aa_index_failure_surfaces_handler_exit_code():
    result = run_cli(
        ["aa-index", "proposal"],
        preconditions_ok=True,
        aa_index_handler=lambda _command, _args: CliResult(exit_code=4, changed=False),
    )

    assert result.exit_code == 4
    assert result.changed is False


@pytest.mark.spec("cli-and-operations::Normalize command dispatches to normalization")
def test_normalize_profiles_command_dispatches_to_normalizer():
    calls = []

    def normalizer(args):
        calls.append(args)
        return CliResult(exit_code=EXIT_CODES["partial_stale"], changed=True, output="rewrote")

    result = run_cli(["normalize-profiles"], preconditions_ok=True, profile_normalizer=normalizer)

    assert result.exit_code == EXIT_CODES["partial_stale"]
    assert result.changed is True
    assert result.output == "rewrote"
    assert len(calls) == 1


@pytest.mark.spec("cli-and-operations::Normalize dry-run reports without writing")
def test_normalize_profiles_dry_run_passes_through_and_reports_result():
    calls = []

    def normalizer(args):
        calls.append(args)
        return CliResult(exit_code=0, changed=False, output="planned rewrite")

    result = run_cli(["normalize-profiles", "--dry-run"], preconditions_ok=True, profile_normalizer=normalizer)

    assert result.exit_code == 0
    assert result.changed is False
    assert result.output == "planned rewrite"
    assert calls[0].dry_run is True


@pytest.mark.spec("cli-and-operations::Apply surfaces gating outcomes")
@pytest.mark.parametrize("exit_code", [5, 6, 7])
def test_apply_and_rollback_surface_guarded_runner_outcomes(exit_code):
    runner = FakeRunner([CliResult(exit_code=exit_code, changed=exit_code != 5)])

    result = run_cli(["apply"], preconditions_ok=True, pipeline_runner=runner)

    assert result.exit_code == exit_code
    assert result.changed is (exit_code != 5)


@pytest.mark.spec("audit-rollback::Roll back a run")
def test_rollback_uses_runner_outcome():
    runner = FakeRunner([CliResult(exit_code=EXIT_CODES["rollback_failed"], changed=True)])

    result = run_cli(["rollback"], preconditions_ok=True, pipeline_runner=runner)

    assert result.exit_code == 7
    assert runner.calls[0][0] == "rollback"


@pytest.mark.spec("cli-and-operations::Dry-run validation")
@pytest.mark.spec("persistence::Dry-run persists nothing")
def test_dry_run_stays_local_and_does_not_call_combo_test():
    runner = FakeRunner([CliResult(exit_code=0, changed=False, combo_test_called=False)])

    result = run_cli(["apply", "--dry-run"], preconditions_ok=True, pipeline_runner=runner)

    assert result.exit_code == 0
    assert result.changed is False
    assert result.combo_test_called is False
    assert runner.calls[0][0] == "apply"
    assert runner.calls[0][1].dry_run is True


@pytest.mark.spec("cli-and-operations::Dry-run runs the stage, not an unconditional success")
def test_dry_run_runs_pipeline_stage_and_surfaces_real_outcome():
    runner = FakeRunner([CliResult(exit_code=EXIT_CODES["external_dependency_failed"], changed=False)])

    result = run_cli(["diff", "--dry-run"], preconditions_ok=True, pipeline_runner=runner)

    assert result.exit_code == EXIT_CODES["external_dependency_failed"]
    assert runner.calls[0][0] == "diff"
    assert runner.calls[0][1].dry_run is True


@pytest.mark.spec("cli-and-operations::Dry-run runs the stage, not an unconditional success")
def test_full_dry_run_runs_pipeline_and_surfaces_real_outcome():
    runner = FakeRunner([CliResult(exit_code=EXIT_CODES["validation_failed"], changed=False)])

    result = run_cli(["full", "--dry-run"], preconditions_ok=True, pipeline_runner=runner)

    assert result.exit_code == EXIT_CODES["validation_failed"]
    assert runner.calls[0][0] == "full"
    assert runner.calls[0][1].dry_run is True


@pytest.mark.spec("cli-and-operations::Explain an endpoint")
@pytest.mark.spec("runtime-bootstrap::Diagnostics read persisted state by default")
def test_explain_endpoint_and_role_read_diagnostics():
    calls = []

    def diagnostics(kind, identifier):
        calls.append((kind, identifier))
        return f"{kind}:{identifier}:score=95 selected"

    endpoint = run_cli(
        ["explain-endpoint", "--endpoint", "endpoint-1"],
        preconditions_ok=True,
        diagnostics_reader=diagnostics,
    )
    role = run_cli(["explain-role", "--role", "coder"], preconditions_ok=True, diagnostics_reader=diagnostics)

    assert endpoint.output == "endpoint:endpoint-1:score=95 selected"
    assert role.output == "role:coder:score=95 selected"
    assert calls == [("endpoint", "endpoint-1"), ("role", "coder")]


@pytest.mark.spec("scheduler::Service fires the daily run")
def test_serve_run_once_invokes_scheduler_runner():
    calls = []

    def scheduler_runner(timestamp):
        calls.append(timestamp)
        return CliResult(exit_code=0, changed=True)

    result = run_cli(["serve", "--run-once"], preconditions_ok=True, scheduler_runner=scheduler_runner)

    assert result.exit_code == 0
    assert result.changed is True
    assert calls and calls[0].endswith("Z")
