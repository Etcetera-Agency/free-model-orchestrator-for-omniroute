def audit_change(
    log: list[dict],
    *,
    run_id: str,
    entity_type: str,
    entity_id: str,
    before,
    after,
    reasons: list[str],
    sources: list[str],
) -> None:
    log.append(
        {
            "run_id": run_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": "update",
            "before_json": before,
            "after_json": after,
            "reason_codes": reasons,
            "source_refs": sources,
        }
    )


def rollback_run(log: list[dict], *, run_id: str, catalog_snapshots: list) -> dict:
    restored = {"catalog_snapshots": catalog_snapshots}
    for entry in log:
        if entry["run_id"] == run_id and entry["entity_type"] == "combo":
            restored[entry["entity_id"]] = entry["before_json"]
    return restored
