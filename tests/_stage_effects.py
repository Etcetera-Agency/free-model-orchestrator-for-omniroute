from fmo.pipeline import StageResult


def effectful_success(stage_name: str, effect: str) -> StageResult:
    return StageResult(
        status="success",
        idempotency_key=f"{stage_name}:effect:{effect}",
        changed=True,
        details={"adapter": stage_name, "effect": effect},
    )


def assert_success_has_declared_effect(record: dict) -> None:
    if record["status"] != "success":
        return
    effect = record["details"].get("effect")
    assert effect in {"repository_write", "omniroute_call", "idempotent_no_change"}
