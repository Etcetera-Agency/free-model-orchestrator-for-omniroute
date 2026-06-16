from enum import Enum


class EndpointState(str, Enum):
    DISCOVERED = "discovered"
    ACCESS_PENDING = "access_pending"
    EXCLUDED_PAID = "excluded_paid"
    EXCLUDED_UNKNOWN = "excluded_unknown"
    FREE_CANDIDATE = "free_candidate"
    PROBE_PENDING = "probe_pending"
    PROBE_FAILED = "probe_failed"
    ACTIVE = "active"
    DEGRADED = "degraded"
    QUOTA_EXHAUSTED = "quota_exhausted"
    REMOVED = "removed"


class ComboState(str, Enum):
    PLANNED = "planned"
    VALIDATED = "validated"
    SNAPSHOT_SAVED = "snapshot_saved"
    APPLIED = "applied"
    SMOKE_FAILED = "smoke_failed"
    ROLLED_BACK = "rolled_back"
    SMOKE_PASSED = "smoke_passed"
    COMMITTED = "committed"


FORBIDDEN_ENDPOINT_TRANSITIONS = {
    (EndpointState.EXCLUDED_UNKNOWN, EndpointState.ACTIVE),
    (EndpointState.QUOTA_EXHAUSTED, EndpointState.ACTIVE),
    (EndpointState.PROBE_FAILED, EndpointState.ACTIVE),
}

ALLOWED_COMBO_TRANSITIONS = {
    (ComboState.PLANNED, ComboState.VALIDATED),
    (ComboState.VALIDATED, ComboState.SNAPSHOT_SAVED),
    (ComboState.SNAPSHOT_SAVED, ComboState.APPLIED),
    (ComboState.APPLIED, ComboState.SMOKE_FAILED),
    (ComboState.SMOKE_FAILED, ComboState.ROLLED_BACK),
    (ComboState.APPLIED, ComboState.SMOKE_PASSED),
    (ComboState.SMOKE_PASSED, ComboState.COMMITTED),
}


def transition_endpoint(current: EndpointState, target: EndpointState) -> EndpointState:
    if (current, target) in FORBIDDEN_ENDPOINT_TRANSITIONS:
        raise ValueError(f"forbidden endpoint transition: {current.value} -> {target.value}")
    return target


def transition_combo(current: ComboState, target: ComboState) -> ComboState:
    if (current, target) not in ALLOWED_COMBO_TRANSITIONS:
        raise ValueError(f"forbidden combo transition: {current.value} -> {target.value}")
    return target
