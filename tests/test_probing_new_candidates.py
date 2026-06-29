"""Unit coverage for admitting bounded new candidates into a seed-bounded probe run.

Exercises `_bounded_new_candidates` directly (no DB): newly onboarded free models
must earn probe evidence instead of being starved by the seed bound (#1).
"""

import pytest

from fmo.composition_stages.probing import _bounded_new_candidates, _select_probe_rows


def _row(id_, model, *, provider="p", connection="c", probe_status="not_run"):
    return {
        "id": id_,
        "provider_model_id": model,
        "omniroute_provider_id": provider,
        "omniroute_connection_id": connection,
        "probe_status": probe_status,
    }


@pytest.mark.spec("probe-runner::New candidates admitted into seed-bounded run")
def test_new_not_run_candidate_is_admitted_alongside_seeds():
    seed = _row("s1", "seed-model", probe_status="passed")
    new = _row("n1", "new-model", probe_status="not_run")
    result = _bounded_new_candidates([seed, new], [seed], per_group=5)
    assert [row["id"] for row in result] == ["n1"]


@pytest.mark.spec("probe-runner::New candidates admitted into seed-bounded run")
def test_seeds_and_failed_are_not_re_added():
    seed = _row("s1", "seed-model", probe_status="passed")
    failed = _row("f1", "failed-model", probe_status="failed")
    result = _bounded_new_candidates([seed, failed], [seed], per_group=5)
    assert result == []


@pytest.mark.spec("probe-runner::New candidates admitted into seed-bounded run")
def test_new_candidates_are_capped_per_provider_connection():
    rows = [_row(f"n{i}", f"m{i}") for i in range(8)]
    result = _bounded_new_candidates(rows, [], per_group=5)
    assert len(result) == 5


@pytest.mark.spec("probe-runner::New candidates admitted into seed-bounded run")
def test_cap_is_per_group_not_global():
    a = [_row(f"a{i}", f"m{i}", provider="pa", connection="c") for i in range(5)]
    b = [_row(f"b{i}", f"m{i}", provider="pb", connection="c") for i in range(5)]
    result = _bounded_new_candidates(a + b, [], per_group=5)
    assert len(result) == 10


@pytest.mark.spec("probe-runner::Steady state probes by quality band and demand")
def test_steady_state_selects_in_band_plus_bounded_unplaced():
    in1 = _row("in1", "in-1", probe_status="passed")
    in2 = _row("in2", "in-2", probe_status="not_run")
    un1 = _row("un1", "un-1", probe_status="not_run")
    un2 = _row("un2", "un-2", probe_status="not_run")
    result = _select_probe_rows(
        [in1, in2, un1, un2],
        has_bands=True,
        band_ids={"in1", "in2"},
        seed_models=set(),
        per_group=1,
    )
    # In-band endpoints are probed (incl. already-passed health re-probe); only a
    # bounded slice of not-yet-placeable candidates is admitted to bootstrap.
    assert [row["id"] for row in result] == ["in1", "in2", "un1"]


@pytest.mark.spec("probe-runner::Steady state probes by quality band and demand")
def test_steady_state_ignores_seed_signal():
    in1 = _row("in1", "in-1", probe_status="not_run")
    seedish = _row("s1", "seed-model", probe_status="not_run")
    result = _select_probe_rows(
        [in1, seedish],
        has_bands=True,
        band_ids={"in1"},
        seed_models={"seed-model"},
        per_group=0,
    )
    # With established bands the seed is forgotten; only band membership matters.
    assert [row["id"] for row in result] == ["in1"]


@pytest.mark.spec("probe-runner::Cold start uses seed signal")
def test_cold_start_uses_seed_then_bounded_new():
    seed = _row("s1", "seed-model", probe_status="passed")
    new = _row("n1", "new-model", probe_status="not_run")
    result = _select_probe_rows(
        [seed, new],
        has_bands=False,
        band_ids=set(),
        seed_models={"seed-model"},
        per_group=5,
    )
    assert [row["id"] for row in result] == ["s1", "n1"]


@pytest.mark.spec("probe-runner::Cold start uses seed signal")
def test_first_run_with_neither_bands_nor_seeds_probes_all():
    rows = [_row("a", "m-a"), _row("b", "m-b")]
    result = _select_probe_rows(
        rows, has_bands=False, band_ids=set(), seed_models=set(), per_group=5
    )
    assert [row["id"] for row in result] == ["a", "b"]
