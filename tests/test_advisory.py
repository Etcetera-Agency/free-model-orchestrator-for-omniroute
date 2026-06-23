import pytest

from fmo.aa_index_runtime import _valid_migration_proposal
from fmo.aa_migration import (
    detect_index_change,
    run_migration_agent,
    select_migration_model,
    validate_migration_proposal,
)
from fmo.smart_review import apply_review_diffs, build_combo_review_context, run_combo_review


def _review_context(role_id="r", endpoints=None):
    endpoints = endpoints or ["e1"]
    return {
        "role_id": role_id,
        "current_combo": endpoints,
        "target_combo": endpoints,
        "deterministic_diff": {"combo_id": f"fmo-{role_id}", "after_endpoint_ids": endpoints},
        "candidate_registry": {"candidates": [{"endpoint_id": endpoint} for endpoint in endpoints]},
    }


@pytest.mark.spec("smart-combo-reviewer::Unknown endpoint add")
@pytest.mark.spec("smart-combo-reviewer::Duplicate add")
def test_reviewer_single_call_and_forbidden_ops_rejected():
    calls = []

    def instructor(payload):
        calls.append(payload)
        return {
            "diffs": [{"op": "add", "role": "r", "endpoint_id": "e2", "position": 1}, {"op": "weight", "role": "r"}]
        }

    review = run_combo_review(instructor, review_context=_review_context(), trigger=True)
    assert len(calls) == 1
    assert review.valid_diffs == [{"op": "add", "role": "r", "endpoint_id": "e2", "position": 1}]
    assert review.rejected[0]["reason"] == "forbidden_op"


@pytest.mark.spec("smart-combo-reviewer::Instructor call fails")
@pytest.mark.spec("smart-combo-reviewer::Reviewer model unavailable")
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
    skipped = run_combo_review(
        lambda payload: (_ for _ in ()).throw(RuntimeError("down")), review_context=_review_context(), trigger=True
    )
    assert combo == {"r": ["e1", "e2"]}
    assert len(audit["rejected"]) == 2
    assert skipped.status == "failed"
    assert skipped.combo_test_called is False


@pytest.mark.spec("smart-combo-reviewer::Trigger disabled")
def test_combo_review_trigger_false_skips_without_instructor_call():
    def instructor(_payload):
        raise AssertionError("instructor should not run")

    review = run_combo_review(instructor, review_context=_review_context(), trigger=False)

    assert review.status == "skipped_trigger"
    assert review.valid_diffs == []


@pytest.mark.spec("smart-combo-reviewer::Unknown endpoint add")
def test_review_diffs_reject_unknown_endpoint_add():
    combo, audit = apply_review_diffs(
        {"r": ["e1"]},
        [{"op": "add", "role": "r", "endpoint_id": "unknown"}],
        candidate_registry={"e1"},
        minimum_combo_size=1,
    )

    assert combo == {"r": ["e1"]}
    assert audit["rejected"][0]["reason"] == "unknown_endpoint"


@pytest.mark.spec("smart-combo-reviewer::Remove below minimum combo size")
def test_review_diffs_reject_remove_below_minimum_combo_size():
    combo, audit = apply_review_diffs(
        {"r": ["e1"]},
        [{"op": "remove", "role": "r", "endpoint_id": "e1"}],
        candidate_registry={"e1"},
        minimum_combo_size=1,
    )

    assert combo == {"r": ["e1"]}
    assert audit["rejected"][0]["reason"] == "minimum_combo_size"


@pytest.mark.spec("smart-combo-reviewer::Missing endpoint remove or move")
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


@pytest.mark.spec("smart-combo-reviewer::Duplicate add")
def test_review_diffs_duplicate_add_is_idempotent():
    combo, audit = apply_review_diffs(
        {"r": ["e1"]},
        [{"op": "add", "role": "r", "endpoint_id": "e1"}],
        candidate_registry={"e1"},
        minimum_combo_size=1,
    )

    assert combo == {"r": ["e1"]}
    assert audit["rejected"] == []


@pytest.mark.spec("smart-combo-reviewer::Reviewer receives deterministic combo context")
@pytest.mark.spec("smart-combo-reviewer::Reviewer receives planning and safety facts")
@pytest.mark.spec("smart-combo-reviewer::Reviewer prompt redacts secrets")
def test_combo_review_context_contains_required_facts_and_redacts_secrets():
    context = build_combo_review_context(
        role_id="routing_fast",
        current_combo=["old"],
        target_combo=[{"kind": "model", "model": "free-chat", "providerId": "provider-a"}],
        deterministic_diff={"combo_id": "fmo-routing_fast", "add": ["endpoint-a"], "after": ["endpoint-a"]},
        targets=[
            {
                "endpoint_id": "endpoint-a",
                "combo_step": {"kind": "model", "model": "free-chat", "providerId": "provider-a"},
                "groups": {"canonical_family": "gemini", "provider_secret": "TOKEN=hidden"},
                "score": 0.9,
            }
        ],
        constraint_report={"apply": True, "diversity": {"canonical_family_concentration": {"gemini": 1}}},
    )

    assert context["role_id"] == "routing_fast"
    assert context["current_combo"] == ["old"]
    assert context["target_combo"][0]["providerId"] == "provider-a"
    assert context["deterministic_diff"]["combo_id"] == "fmo-routing_fast"
    assert "role_requirements" in context
    assert "demand_forecast" in context
    assert "allocation_constraint_report" in context
    assert context["candidate_registry"]["candidates"][0]["endpoint_id"] == "endpoint-a"
    assert "quota_summary" in context
    assert "diversity_summary" in context
    assert "validation_report" in context
    assert "apply_precondition_summary" in context
    assert "hidden" not in str(context)


@pytest.mark.spec("smart-combo-reviewer::Reviewer prompt remains bounded and complete")
def test_combo_review_context_summarizes_large_candidate_registry_without_dropping_sections():
    targets = [
        {
            "endpoint_id": f"endpoint-{index:02d}",
            "combo_step": {"kind": "model", "model": f"model-{index:02d}", "providerId": "provider-a"},
            "groups": {"canonical_family": "family"},
            "score": index,
        }
        for index in range(30)
    ]

    context = build_combo_review_context(
        role_id="routing_fast",
        current_combo=[],
        target_combo=[],
        deterministic_diff={"combo_id": "fmo-routing_fast"},
        targets=targets,
        constraint_report={"apply": True},
        max_candidates=5,
    )

    assert len(context["candidate_registry"]["candidates"]) == 5
    assert context["candidate_registry"]["omitted_candidates"] == 25
    for section in (
        "role_id",
        "current_combo",
        "target_combo",
        "deterministic_diff",
        "role_requirements",
        "demand_forecast",
        "allocation_constraint_report",
        "candidate_registry",
        "quota_summary",
        "diversity_summary",
        "validation_report",
        "apply_precondition_summary",
    ):
        assert section in context


@pytest.mark.spec("aa-index-migration::New major index arrives")
def test_aa_index_change_freezes_thresholds_and_keeps_combos():
    migration = detect_index_change(
        active_version="v1", fetched_version="v2", thresholds={"r": 40}, combos={"r": ["e1"]}
    )
    assert migration.created is True
    assert migration.freeze_thresholds is True
    assert migration.current_combos == {"r": ["e1"]}
    assert migration.production_recalculation_stopped is True


@pytest.mark.spec("aa-index-migration::Proposal generation")
def test_migration_agent_selects_highest_intelligence_and_validates_approval():
    selected = select_migration_model(
        [
            {"endpoint": "e1", "intelligence_index": 40, "available": True},
            {"endpoint": "e2", "intelligence_index": 70, "available": True},
        ]
    )
    proposal = run_migration_agent(
        lambda model: {"index_version": "v2", "roles": {"r": {"metric": "intelligence_index", "threshold_value": 50}}},
        {
            "old_index_version": "v1",
            "new_index_version": "v2",
            "roles": [{"role_id": "r"}],
            "capacity_summary": {},
            "percentile_mapping": {},
        },
    )
    validation = validate_migration_proposal(
        proposal,
        new_version="v2",
        role_capacity={"r": {"eligible": 4, "minimum": 2, "quota_ok": True, "quality_ok": True}},
        approved=False,
    )
    approved = validate_migration_proposal(
        proposal,
        new_version="v2",
        role_capacity={"r": {"eligible": 4, "minimum": 2, "quota_ok": True, "quality_ok": True}},
        approved=True,
    )
    assert selected["endpoint"] == "e2"
    assert validation.can_rollout is False
    assert validation.needs_approval is True
    assert approved.can_rollout is True


@pytest.mark.spec("aa-index-migration::No migration model")
@pytest.mark.spec("aa-index-migration::Smoke test fails after rollout")
def test_no_model_and_smoke_failure_keep_or_rollback_production():
    assert select_migration_model([]) is None
    proposal = {"index_version": "v2", "roles": {"r": {"metric": "coding_index", "threshold_value": 999}}}
    with pytest.raises(ValueError):
        validate_migration_proposal(
            proposal,
            new_version="v2",
            role_capacity={"r": {"eligible": 0, "minimum": 2, "quota_ok": False, "quality_ok": False}},
            approved=True,
        )


@pytest.mark.spec("aa-index-migration::Invalid proposal enters repair loop")
def test_migration_repair_loop_passes_validation_errors_and_persists_repaired_proposal():
    class Runtime:
        def __init__(self):
            self.calls = []

        def complete(self, *, site, context, response_model):
            self.calls.append({"site": site.name, "context": context})
            if len(self.calls) == 1:
                return response_model(
                    index_version="wrong", roles={"r": {"metric": "intelligence_index", "threshold_value": 50}}
                )
            return response_model(
                index_version="v2", roles={"r": {"metric": "intelligence_index", "threshold_value": 50}}
            )

    context = {
        "new_index_version": "v2",
        "role_capacity": {"r": {"eligible": 2, "minimum": 1, "quota_ok": True, "quality_ok": True}},
    }

    runtime = Runtime()
    proposal, report = _valid_migration_proposal(runtime, context)

    assert proposal["index_version"] == "v2"
    assert report["attempts"][0]["validation_errors"] == ["wrong_index_version"]
    assert report["attempts"][1]["repair_errors"] == ["wrong_index_version"]


@pytest.mark.spec("aa-index-migration::Unrepaired proposal fails closed")
def test_migration_repair_loop_fails_closed_after_three_invalid_attempts():
    class Runtime:
        def complete(self, *, site, context, response_model):
            return response_model(
                index_version="wrong", roles={"r": {"metric": "intelligence_index", "threshold_value": 50}}
            )

    context = {
        "new_index_version": "v2",
        "role_capacity": {"r": {"eligible": 2, "minimum": 1, "quota_ok": True, "quality_ok": True}},
    }

    proposal, report = _valid_migration_proposal(Runtime(), context)

    assert proposal is None
    assert report["status"] == "migration_needs_manual_review"
    assert len(report["attempts"]) == 3
