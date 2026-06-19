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
def test_dry_run_stays_local_and_does_not_call_combo_test():
    runner = FakeRunner()

    result = run_cli(["apply", "--dry-run"], preconditions_ok=True, pipeline_runner=runner)

    assert result.exit_code == 0
    assert result.changed is False
    assert result.combo_test_called is False
    assert runner.calls == []


@pytest.mark.spec("cli-and-operations::Explain an endpoint")
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
