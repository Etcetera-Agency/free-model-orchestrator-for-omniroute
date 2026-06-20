import pytest


@pytest.mark.xfail(reason="stage adapter wiring lands in subsequent OpenSpec slices", strict=True)
@pytest.mark.spec("pipeline-orchestration::Probe respects confirmed free capacity")
@pytest.mark.spec("pipeline-orchestration::Probe persists results and excludes failures")
@pytest.mark.spec("pipeline-orchestration::Telemetry sync writes normalized rows")
@pytest.mark.spec("pipeline-orchestration::Quota sync writes remaining-quota state")
def test_probe_telemetry_stage_effects_are_not_wired_yet():
    assert False


@pytest.mark.xfail(reason="stage adapter wiring lands in subsequent OpenSpec slices", strict=True)
@pytest.mark.spec("pipeline-orchestration::Scoring persists per-role scores")
@pytest.mark.spec("pipeline-orchestration::Allocation persists one combo plan per role")
@pytest.mark.spec("pipeline-orchestration::Oversubscription gate blocks zero-capacity pool")
@pytest.mark.spec("pipeline-orchestration::Diff is computed without mutating OmniRoute")
def test_scoring_allocation_stage_effects_are_not_wired_yet():
    assert False


@pytest.mark.xfail(reason="stage adapter wiring lands in subsequent OpenSpec slices", strict=True)
@pytest.mark.spec("combo-applier::Production apply smoke-tests applied combos")
@pytest.mark.spec("combo-applier::Fabricated smoke signal rejected")
@pytest.mark.spec("pipeline-orchestration::Production apply runs the real smoke test")
@pytest.mark.spec("pipeline-orchestration::Failing guard blocks apply")
@pytest.mark.spec("pipeline-orchestration::Smoke failure rolls back")
@pytest.mark.spec("pipeline-orchestration::Audit persists records")
def test_apply_audit_stage_effects_are_not_wired_yet():
    assert False
