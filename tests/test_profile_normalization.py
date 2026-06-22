from pathlib import Path

import pytest
import yaml

from fmo.profile_normalization import normalize_profiles


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.spec("profile-normalization::Raw slot maps to combo with same canonical model")
def test_raw_slot_maps_to_existing_combo_by_canonical_model(tmp_path):
    config = tmp_path / "profiles" / "default" / "config.yaml"
    _write_yaml(
        config,
        {
            "model": "fmo-default",
            "auxiliary": {"vision": {"provider": "google", "model": "google/gemini-2.5-flash"}},
        },
    )

    result = normalize_profiles(
        tmp_path,
        current_combos={
            "fmo-default": ["openrouter/deepseek-chat"],
            "fmo-vision": ["openrouter/gemini-2.5-flash"],
        },
        dry_run=False,
    )

    updated = _read_yaml(config)
    assert result.changed is True
    assert updated["auxiliary"]["vision"]["model"] == "fmo-vision"
    assert updated["auxiliary"]["vision"]["provider"] == "omniroute"


@pytest.mark.spec("profile-normalization::Missing combo falls back to default profile combo")
def test_missing_combo_falls_back_to_default_profile_combo_without_creating_combo(tmp_path):
    config = tmp_path / "profiles" / "default" / "config.yaml"
    _write_yaml(config, {"model": "fmo-default", "auxiliary": {"code": {"model": "fmo-missing"}}})

    result = normalize_profiles(
        tmp_path,
        current_combos={"fmo-default": ["openrouter/deepseek-chat"]},
        dry_run=False,
    )

    updated = _read_yaml(config)
    assert [rewrite.new for rewrite in result.rewrites] == ["fmo-default"]
    assert updated["auxiliary"]["code"]["model"] == "fmo-default"


@pytest.mark.spec("profile-normalization::Conforming and auto slots are untouched")
def test_conforming_and_auto_slots_are_untouched(tmp_path):
    config = tmp_path / "profiles" / "default" / "config.yaml"
    payload = {
        "model": "fmo-default",
        "auxiliary": {
            "existing": {"provider": "omniroute", "model": "fmo-existing"},
            "auto": {"provider": "auto", "model": "auto"},
            "empty": {"provider": "omniroute"},
        },
    }
    _write_yaml(config, payload)

    result = normalize_profiles(
        tmp_path,
        current_combos={"fmo-default": ["openrouter/deepseek-chat"], "fmo-existing": ["openrouter/qwen"]},
        dry_run=False,
    )

    assert result.rewrites == []
    assert _read_yaml(config) == payload


@pytest.mark.spec("profile-normalization::Dry-run writes nothing and backs up config")
def test_dry_run_reports_rewrites_without_writes_or_backups(tmp_path):
    config = tmp_path / "profiles" / "default" / "config.yaml"
    _write_yaml(config, {"model": "fmo-default", "auxiliary": {"vision": {"model": "google/gemini"}}})
    before = config.read_text(encoding="utf-8")

    result = normalize_profiles(
        tmp_path,
        current_combos={"fmo-default": ["openrouter/deepseek-chat"], "fmo-vision": ["openrouter/gemini"]},
        dry_run=True,
    )

    assert [(rewrite.slot, rewrite.old, rewrite.new) for rewrite in result.rewrites] == [
        ("auxiliary.vision", "google/gemini", "fmo-vision")
    ]
    assert result.changed is False
    assert result.backups == []
    assert config.read_text(encoding="utf-8") == before
    assert not config.with_suffix(".yaml.bak").exists()


@pytest.mark.spec("profile-normalization::Apply backs up before atomic rewrite")
def test_apply_backs_up_before_rewrite_and_preserves_other_keys(tmp_path):
    config = tmp_path / "config.yaml"
    _write_yaml(
        config,
        {
            "model": "fmo-default",
            "theme": "dark",
            "gateway": {
                "platforms": {
                    "slack": {
                        "model": "anthropic/claude-haiku",
                        "auxiliary": {"vision": {"model": "google/gemini"}},
                    }
                }
            },
        },
    )

    result = normalize_profiles(
        tmp_path,
        current_combos={
            "fmo-default": ["openrouter/deepseek-chat"],
            "fmo-chat": ["openrouter/claude-haiku"],
            "fmo-vision": ["openrouter/gemini"],
        },
        dry_run=False,
    )

    backup = config.with_suffix(".yaml.bak")
    updated = _read_yaml(config)
    assert result.backups == [backup]
    assert backup.exists()
    assert _read_yaml(backup)["gateway"]["platforms"]["slack"]["model"] == "anthropic/claude-haiku"
    assert updated["theme"] == "dark"
    assert updated["gateway"]["platforms"]["slack"]["model"] == "fmo-chat"
    assert updated["gateway"]["platforms"]["slack"]["auxiliary"]["vision"]["model"] == "fmo-vision"
    assert updated["gateway"]["platforms"]["slack"]["auxiliary"]["vision"]["provider"] == "omniroute"
