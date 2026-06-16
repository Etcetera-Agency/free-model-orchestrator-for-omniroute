from dataclasses import dataclass


@dataclass(frozen=True)
class ApplyPreconditions:
    db_available: bool
    snapshot_saved: bool
    desired_state_valid: bool
    quota_safe: bool
    probes_passed: bool


def check_apply_preconditions(preconditions: ApplyPreconditions) -> None:
    failed = [
        name
        for name, passed in (
            ("db_available", preconditions.db_available),
            ("snapshot_saved", preconditions.snapshot_saved),
            ("desired_state_valid", preconditions.desired_state_valid),
            ("quota_safe", preconditions.quota_safe),
            ("probes_passed", preconditions.probes_passed),
        )
        if not passed
    ]
    if failed:
        raise ValueError(f"apply preconditions failed: {', '.join(failed)}")
