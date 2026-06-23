import pytest

from fmo.hermes_inventory import (
    ComboGridCell,
    Consumer,
    DescribingUnit,
    InspectorForecast,
    IntelligenceVerdict,
    Inventory,
    RoleQualityAnchor,
    anchor_after_rebalance_event,
    assemble_intelligence_prompt,
    bootstrap_combo_payload,
    build_hermes_inventory,
    demand_driven_combo_profiles,
    describing_units,
    forecast_with_quality_choice,
    inventory_diff,
    quality_band_for_anchor,
    role_quality_anchors,
    select_combo_grid_cell,
)


class SequenceRuntime:
    def __init__(self, *responses, fail=False):
        self.responses = list(responses)
        self.fail = fail
        self.calls = []

    def complete(self, *, site, context, response_model):
        self.calls.append({"site": site, "context": context, "response_model": response_model})
        if self.fail:
            raise RuntimeError("inspector unavailable")
        payload = self.responses.pop(0)
        return response_model(**payload)


def _consumer(role, consumer_type, consumer, text="", *, cadence="daily", capabilities=()):
    return Consumer(
        role_id=role,
        consumer_type=consumer_type,
        consumer=consumer,
        cadence=cadence,
        calls_per_run=1,
        describing_text=text,
        required_capabilities=tuple(capabilities),
    )


@pytest.mark.spec("hermes-inventory::Each describing unit is assessed individually")
def test_profile_cron_and_aux_units_are_prompted_separately(tmp_path):
    profile_dir = tmp_path / "profiles" / "research"
    profile_dir.mkdir(parents=True)
    (profile_dir / "config.yaml").write_text(
        "model: fmo-research\nauxiliary:\n  vision:\n    model: fmo-vision\n    purpose: inspect screenshots\n"
    )
    (profile_dir / "SOUL.md").write_text("reason about papers")
    (profile_dir / "AGENTS.md").write_text("use careful citations")
    inventory = build_hermes_inventory(
        profiles={"profiles": [{"name": "research", "path": str(profile_dir), "gateway_running": False}]},
        cron_jobs={
            "jobs": [
                {
                    "id": "daily",
                    "model": "fmo-research",
                    "schedule": {"kind": "cron", "expr": "0 9 * * *"},
                    "prompt": "summarize new arxiv papers",
                }
            ]
        },
    )
    runtime = SequenceRuntime(
        {"capability_axis": "agentic_index", "tier": "high", "confidence": "high"},
        {"capability_axis": "coding_index", "tier": "low", "confidence": "medium"},
        {"capability_axis": "intelligence_index", "tier": "medium", "confidence": "low"},
    )

    role_quality_anchors(inventory, runtime)

    prompts = [call["context"]["prompt"] for call in runtime.calls]
    assert len(prompts) == 3
    assert any("SOUL.md" in prompt and "AGENTS.md" in prompt for prompt in prompts)
    assert any("summarize new arxiv papers" in prompt for prompt in prompts)
    assert any("inspect screenshots" in prompt for prompt in prompts)


@pytest.mark.spec("hermes-inventory::Axis and anchor set the band centre, not its edges")
def test_axis_and_anchor_drive_quality_band_centre_not_edges():
    anchor = RoleQualityAnchor("role", "intelligence_index", "high", 80, "high", "intelligence_inspector")
    band = quality_band_for_anchor(
        anchor,
        candidates=[
            {"quality": 40, "capacity": 100, "confirmed_free": True},
            {"quality": 80, "capacity": 100, "confirmed_free": True},
            {"quality": 95, "capacity": 100, "confirmed_free": True},
        ],
        protected_requests=150,
    )

    assert anchor.capability_axis == "intelligence_index"
    assert band.minimum <= 80 <= band.maximum
    assert (band.minimum, band.maximum) != (80, 80)


@pytest.mark.spec("hermes-inventory::Shared combo takes the most demanding unit")
def test_shared_role_uses_most_demanding_unit_anchor_and_axis():
    inventory = Inventory(
        [
            _consumer("shared", "agent_profile", "research", "deep reasoning"),
            _consumer("shared", "cron_job", "cleanup", "mechanical cleanup"),
        ]
    )
    runtime = SequenceRuntime(
        {"capability_axis": "agentic_index", "tier": "high", "confidence": "high"},
        {"capability_axis": "coding_index", "tier": "low", "confidence": "medium"},
    )

    anchor = role_quality_anchors(inventory, runtime)["shared"]

    assert anchor.anchor == 80
    assert anchor.capability_axis == "agentic_index"


@pytest.mark.spec("hermes-inventory::Bare webhook role floors without an LLM call")
def test_descriptionless_role_gets_floor_without_inspector_call():
    runtime = SequenceRuntime()
    anchors = role_quality_anchors(Inventory([_consumer("webhook", "webhook", "hook")]), runtime)

    assert anchors["webhook"].anchor == 20
    assert anchors["webhook"].source == "adequacy_floor"
    assert runtime.calls == []


@pytest.mark.spec("hermes-inventory::Unchanged unit reuses its cached verdict")
def test_unchanged_unit_hash_reuses_cached_verdict():
    consumer = _consumer("role", "agent_profile", "profile", "same persona")
    content_hash = describing_units(Inventory([consumer]))[0].content_hash
    cache = {"role:agent_profile:profile": IntelligenceVerdict("coding_index", "medium", "high", 50, content_hash)}
    runtime = SequenceRuntime()

    anchor = role_quality_anchors(Inventory([consumer]), runtime, cache=cache)["role"]

    assert anchor.anchor == 50
    assert runtime.calls == []


@pytest.mark.spec("hermes-inventory::Cadence change does not re-run the intelligence Inspector")
def test_cadence_change_refreshes_demand_not_intelligence_units():
    old = Inventory([_consumer("role", "cron_job", "job", "same prompt", cadence="daily")])
    new = Inventory([_consumer("role", "cron_job", "job", "same prompt", cadence="hourly")])

    diff = inventory_diff(old, new)

    assert diff.forecast_stale is True
    assert diff.run_inspector is True
    assert diff.intelligence_stale_units == ()


@pytest.mark.spec("hermes-inventory::Changed persona re-assesses only its unit")
def test_changed_persona_reassesses_only_changed_unit():
    old = Inventory(
        [
            _consumer("role", "agent_profile", "a", "old soul"),
            _consumer("role", "cron_job", "job", "same prompt"),
        ]
    )
    new = Inventory(
        [
            _consumer("role", "agent_profile", "a", "new soul"),
            _consumer("role", "cron_job", "job", "same prompt"),
        ]
    )

    assert inventory_diff(old, new).intelligence_stale_units == ("role:agent_profile:a",)


@pytest.mark.spec("hermes-inventory::Main role snaps to a reusable grid combo")
def test_main_role_reuses_matching_grid_combo():
    cell = select_combo_grid_cell(
        role_id="research",
        capability_axis="agentic_index",
        tier="high",
        required_capabilities=set(),
        minimum_context_window=128000,
        grid=[
            ComboGridCell(
                "fmo-grid-agt-high",
                "agentic_index",
                "high",
                80,
                minimum_context_window=128000,
            )
        ],
    )

    assert cell.combo_id == "fmo-grid-agt-high"
    assert cell.reusable is True


@pytest.mark.spec("hermes-inventory::Auxiliary role snaps to a cheap capability-matched combo")
def test_auxiliary_combo_requires_matching_capability_without_inspector_call():
    runtime = SequenceRuntime()
    inventory = Inventory([_consumer("vision", "auxiliary", "profile:vision", "", capabilities=("vision",))])
    cell = select_combo_grid_cell(
        role_id="vision",
        capability_axis="intelligence_index",
        tier="low",
        required_capabilities={"vision"},
        minimum_context_window=0,
        auxiliary=True,
        grid=[
            ComboGridCell("fmo-grid-aux-text", "intelligence_index", "low", 20, auxiliary=True),
            ComboGridCell(
                "fmo-grid-aux-vision",
                "intelligence_index",
                "low",
                20,
                required_capabilities=("vision",),
                auxiliary=True,
            ),
        ],
    )

    assert role_quality_anchors(inventory, runtime)["vision"].source == "adequacy_floor"
    assert runtime.calls == []
    assert cell.combo_id == "fmo-grid-aux-vision"


@pytest.mark.spec("hermes-inventory::Context window is part of the cell profile")
def test_context_window_must_match_grid_cell_profile():
    cell = select_combo_grid_cell(
        role_id="long-context",
        capability_axis="intelligence_index",
        tier="medium",
        required_capabilities=set(),
        minimum_context_window=1_000_000,
        grid=[
            ComboGridCell("small", "intelligence_index", "medium", 50, minimum_context_window=128000),
            ComboGridCell("large", "intelligence_index", "medium", 50, minimum_context_window=1_000_000),
        ],
    )

    assert cell.combo_id == "large"


@pytest.mark.spec("hermes-inventory::Grid is demand-driven, not cartesian")
def test_grid_profiles_are_derived_from_occurring_role_tuples_only():
    inventory = Inventory(
        [
            _consumer("chat", "agent_profile", "default", "chat", capabilities=()),
            _consumer("vision", "auxiliary", "default:vision", "", capabilities=("vision",)),
        ]
    )
    profiles = demand_driven_combo_profiles(
        inventory,
        {"chat": RoleQualityAnchor("chat", "intelligence_index", "medium", 50, "high", "test")},
    )

    assert profiles == {
        ("intelligence_index", "medium", (), 0, False),
        ("intelligence_index", "low", ("vision",), 0, True),
    }


@pytest.mark.spec("hermes-inventory::Singleton profile mints a unique combo")
@pytest.mark.spec("hermes-inventory::New agent with a novel profile mints a unique combo")
def test_singleton_profile_mints_unique_combo_when_no_cell_fits():
    cell = select_combo_grid_cell(
        role_id="rare-agent",
        capability_axis="coding_index",
        tier="high",
        required_capabilities={"vision"},
        minimum_context_window=1_000_000,
        grid=[],
    )

    assert cell.combo_id == "fmo-unique-role-rare-agent"
    assert cell.reusable is False


@pytest.mark.spec("hermes-inventory::Bootstrap seeds one model, agents grow the combo")
def test_bootstrap_payload_uses_single_seed_model():
    payload = bootstrap_combo_payload(
        ComboGridCell("fmo-grid-int-high", "intelligence_index", "high", 80),
        seed_model="provider/model",
        provider_id="provider",
    )

    assert payload["models"] == [{"kind": "model", "model": "provider/model", "providerId": "provider", "weight": 0}]
    assert payload["strategy"] == "priority"


@pytest.mark.spec("hermes-inventory::Quota recalibration reorders without re-anchoring")
def test_rebalance_event_keeps_anchor_until_persona_hash_changes():
    anchor = RoleQualityAnchor("role", "agentic_index", "high", 80, "high", "intelligence_inspector")

    assert anchor_after_rebalance_event(anchor, persona_hash_changed=False) is anchor
    assert anchor_after_rebalance_event(anchor, persona_hash_changed=True) is None


@pytest.mark.spec("hermes-inventory::Thin-corner shortfall degrades rather than re-anchors")
def test_thin_corner_capacity_degrades_without_lowering_anchor():
    anchor = RoleQualityAnchor("role", "agentic_index", "high", 80, "high", "intelligence_inspector")
    band = quality_band_for_anchor(
        anchor,
        candidates=[{"quality": 90, "capacity": 1, "confirmed_free": True}],
        protected_requests=10,
    )

    assert band.degraded is True
    assert anchor.anchor == 80


@pytest.mark.spec("hermes-inventory::Inspector failure falls back to seed anchor")
def test_inspector_failure_uses_seed_anchor_and_demand_forecast_can_keep_choice():
    seed = RoleQualityAnchor("role", "coding_index", "medium", 55, "seed", "seed")
    anchors = role_quality_anchors(
        Inventory([_consumer("role", "agent_profile", "profile", "hard task")]),
        SequenceRuntime(fail=True),
        seed_anchors={"role": seed},
    )
    forecast = forecast_with_quality_choice(
        InspectorForecast(
            role="role",
            expected_calls=3,
            average_input_tokens=100,
            average_output_tokens=50,
            confidence="medium",
        ),
        anchors["role"],
    )

    assert anchors["role"] == seed
    assert forecast.model_choice == {"axis": "coding_index", "tier": "medium", "anchor": 55}


def test_intelligence_prompt_redacts_and_limits_secrets():
    unit = DescribingUnit("role", "cron_job", "job", "role:cron_job:job", "token=secret " * 100, "hash")

    prompt = assemble_intelligence_prompt(unit, secrets={"TOKEN": "secret"}, max_prompt_chars=80)

    assert "secret" not in prompt
    assert len(prompt) == 80
