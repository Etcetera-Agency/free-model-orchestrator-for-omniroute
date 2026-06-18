import pytest

from fmo.aa_migration import run_migration_agent
from fmo.hermes_inventory import run_inspector
from fmo.llm_runtime import LlmRuntimeError, LlmSiteConfig, complete_with_adapter
from fmo.quota_research import QuotaClaimResponse, run_quota_inspector
from fmo.smart_review import run_combo_review

from _fixtures import fixture_body


class RecordingCompletionTransport:
    def __init__(self, completions):
        self.completions = completions
        self.calls = []

    def __call__(self, payload):
        self.calls.append(payload)
        return self.completions[payload["site"].replace("-", "_")]


def _transport():
    return RecordingCompletionTransport(fixture_body("omniroute_structured_llm_completions"))


@pytest.mark.spec("llm-runtime::All sites use the adapter")
def test_all_structured_llm_sites_use_shared_adapter_and_validate_pydantic_outputs():
    transport = _transport()

    quota_claim = run_quota_inspector(transport, "quota prompt")
    forecast = run_inspector(transport, "forecast prompt")
    review = run_combo_review(transport, deterministic_combo={"research_scout": ["free:model-b"]}, trigger=True)
    migration = run_migration_agent(transport, {"endpoint": "free:model-a", "available": True})

    assert quota_claim.amount == 60
    assert forecast.role == "research_scout"
    assert review.valid_diffs == [{"op": "add", "role": "research_scout", "endpoint_id": "free:model-a", "position": 1}]
    assert review.rejected == [{"diff": {"op": "weight", "role": "research_scout"}, "reason": "forbidden_op"}]
    assert migration["index_version"] == "2026-06-18-aa-free"
    assert [call["site"] for call in transport.calls] == [
        "quota-research-inspector",
        "hermes-inspector",
        "smart-combo-reviewer",
        "aa-index-migration",
    ]
    assert all(call["mode"] == "json_schema" for call in transport.calls)
    assert all(call["response_model"] for call in transport.calls)


def test_adapter_redacts_prompt_and_applies_site_limit_before_transport_call():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"metric": "requests", "amount": 1, "window": "day", "evidence": ["fixture"], "hard_stop": False}

    completion = complete_with_adapter(
        transport,
        site=LlmSiteConfig(name="quota-research-inspector", model="free:model", max_prompt_chars=42),
        context={"prompt": "Bearer secret-token " + ("x" * 100)},
        response_model=QuotaClaimResponse,
    )

    assert completion.amount == 1
    assert "secret-token" not in calls[0]["prompt"]
    assert len(calls[0]["prompt"]) == 42
    assert calls[0]["model"] == "free:model"


@pytest.mark.spec("llm-runtime::Malformed completion repaired or rejected")
def test_malformed_completion_uses_repair_path_and_unrepairable_result_fails_deterministically():
    completions = fixture_body("omniroute_structured_llm_completions")
    transport = RecordingCompletionTransport({"smart_combo_reviewer": completions["smart_combo_reviewer"]})
    review = run_combo_review(transport, deterministic_combo={"research_scout": ["free:model-b"]}, trigger=True)

    assert review.status == "ok"

    with pytest.raises(LlmRuntimeError):
        complete_with_adapter(
            lambda _payload: completions["malformed_unrepairable"],
            site=LlmSiteConfig(name="quota-research-inspector", model="free:model"),
            context={"prompt": "quota prompt"},
            response_model=QuotaClaimResponse,
        )


@pytest.mark.spec("llm-runtime::Advisory site fails open")
def test_advisory_sites_fail_open_when_llm_returns_nothing_usable():
    review = run_combo_review(lambda _payload: "", deterministic_combo={"r": ["e1"]}, trigger=True)
    migration = run_migration_agent(lambda _payload: "", {"endpoint": "free:model-a", "available": True})

    assert review.status == "failed"
    assert review.combo_test_called is False
    assert migration == {"status": "advisory_unavailable"}
