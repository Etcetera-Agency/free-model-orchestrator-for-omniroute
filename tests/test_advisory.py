import pytest

from fmo.aa_migration import (
    detect_index_change,
    run_migration_agent,
    select_migration_model,
    validate_migration_proposal,
)
from fmo.smart_review import apply_review_diffs, run_combo_review


def test_reviewer_single_call_and_forbidden_ops_rejected():
    calls = []

    def instructor(payload):
        calls.append(payload)
        return {"diffs": [{"op": "add", "role": "r", "endpoint_id": "e2", "position": 1}, {"op": "weight", "role": "r"}]}

    review = run_combo_review(instructor, deterministic_combo={"r": ["e1"]}, trigger=True)
    assert len(calls) == 1
    assert review.valid_diffs == [{"op": "add", "role": "r", "endpoint_id": "e2", "position": 1}]
    assert review.rejected[0]["reason"] == "forbidden_op"


def test_review_diffs_validated_independently_fail_open_no_combo_test():
    combo, audit = apply_review_diffs(
        {"r": ["e1"]},
        [
            {"op": "add", "role": "r", "endpoint_id": "e2", "position": 1},
            {"op": "move", "role": "r", "endpoint_id": "missing", "position": 0},
            {"op": "remove", "role": "r", "endpoint_id": "e1"},
        ],
        candidate_registry={"e1", "e2"},
        minimum_combo_size=2,
    )
    skipped = run_combo_review(lambda payload: (_ for _ in ()).throw(RuntimeError("down")), deterministic_combo={"r": ["e1"]}, trigger=True)
    assert combo == {"r": ["e1", "e2"]}
    assert len(audit["rejected"]) == 2
    assert skipped.status == "failed"
    assert skipped.combo_test_called is False


def test_combo_review_trigger_false_skips_without_instructor_call():
    def instructor(_payload):
        raise AssertionError("instructor should not run")

    review = run_combo_review(instructor, deterministic_combo={"r": ["e1"]}, trigger=False)

    assert review.status == "skipped_trigger"
    assert review.valid_diffs == []


def test_review_diffs_reject_unknown_endpoint_add():
    combo, audit = apply_review_diffs(
        {"r": ["e1"]},
        [{"op": "add", "role": "r", "endpoint_id": "unknown"}],
        candidate_registry={"e1"},
        minimum_combo_size=1,
    )

    assert combo == {"r": ["e1"]}
    assert audit["rejected"][0]["reason"] == "unknown_endpoint"


def test_review_diffs_reject_remove_below_minimum_combo_size():
    combo, audit = apply_review_diffs(
        {"r": ["e1"]},
        [{"op": "remove", "role": "r", "endpoint_id": "e1"}],
        candidate_registry={"e1"},
        minimum_combo_size=1,
    )

    assert combo == {"r": ["e1"]}
    assert audit["rejected"][0]["reason"] == "minimum_combo_size"


@pytest.mark.parametrize("op", ["remove", "move"])
def test_review_diffs_reject_missing_endpoint_remove_or_move(op):
    combo, audit = apply_review_diffs(
        {"r": ["e1", "e2"]},
        [{"op": op, "role": "r", "endpoint_id": "missing", "position": 0}],
        candidate_registry={"e1", "e2"},
        minimum_combo_size=1,
    )

    assert combo == {"r": ["e1", "e2"]}
    assert audit["rejected"][0]["reason"] == "endpoint_missing"


def test_review_diffs_duplicate_add_is_idempotent():
    combo, audit = apply_review_diffs(
        {"r": ["e1"]},
        [{"op": "add", "role": "r", "endpoint_id": "e1"}],
        candidate_registry={"e1"},
        minimum_combo_size=1,
    )

    assert combo == {"r": ["e1"]}
    assert audit["rejected"] == []


def test_aa_index_change_freezes_thresholds_and_keeps_combos():
    migration = detect_index_change(active_version="v1", fetched_version="v2", thresholds={"r": 40}, combos={"r": ["e1"]})
    assert migration.created is True
    assert migration.freeze_thresholds is True
    assert migration.current_combos == {"r": ["e1"]}
    assert migration.production_recalculation_stopped is True


def test_migration_agent_selects_highest_intelligence_and_validates_approval():
    selected = select_migration_model(
        [
            {"endpoint": "e1", "intelligence_index": 40, "available": True},
            {"endpoint": "e2", "intelligence_index": 70, "available": True},
        ]
    )
    proposal = run_migration_agent(lambda model: {"index_version": "v2", "roles": {"r": {"metric": "intelligence_index", "threshold": 50}}}, selected)
    validation = validate_migration_proposal(
        proposal,
        new_version="v2",
        role_capacity={"r": {"eligible": 4, "minimum": 2, "quota_ok": True, "quality_ok": True}},
        approved=False,
    )
    approved = validate_migration_proposal(proposal, new_version="v2", role_capacity={"r": {"eligible": 4, "minimum": 2, "quota_ok": True, "quality_ok": True}}, approved=True)
    assert selected["endpoint"] == "e2"
    assert validation.can_rollout is False
    assert validation.needs_approval is True
    assert approved.can_rollout is True


def test_no_model_and_smoke_failure_keep_or_rollback_production():
    assert select_migration_model([]) is None
    proposal = {"index_version": "v2", "roles": {"r": {"metric": "coding_index", "threshold": 999}}}
    with pytest.raises(ValueError):
        validate_migration_proposal(proposal, new_version="v2", role_capacity={"r": {"eligible": 0, "minimum": 2, "quota_ok": False, "quality_ok": False}}, approved=True)
