from __future__ import annotations

import os
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProfileRewrite:
    config_path: Path
    slot: str
    old: str
    new: str


@dataclass(frozen=True)
class ProfileNormalizationResult:
    rewrites: list[ProfileRewrite]
    changed: bool
    backups: list[Path]

    @property
    def exit_code(self) -> int:
        return 0


def normalize_profiles(
    home: str | Path,
    *,
    current_combos: dict[str, list[str]],
    dry_run: bool,
) -> ProfileNormalizationResult:
    home = Path(home)
    configs = _profile_configs(home)
    default_combo = _default_profile_combo(home, configs)
    combo_by_canonical = _combo_by_canonical(current_combos)
    existing_combos = set(current_combos)
    plan: list[ProfileRewrite] = []

    for config_path, config in configs:
        for slot, value in _slot_values(config):
            target = _rewrite_target(
                value,
                existing_combos=existing_combos,
                combo_by_canonical=combo_by_canonical,
                default_combo=default_combo,
            )
            if target is not None and target != value:
                plan.append(ProfileRewrite(config_path=config_path, slot=slot, old=value, new=target))

    if dry_run or not plan:
        return ProfileNormalizationResult(rewrites=plan, changed=False, backups=[])

    backups = []
    rewrites_by_config: dict[Path, list[ProfileRewrite]] = defaultdict(list)
    for rewrite in plan:
        rewrites_by_config[rewrite.config_path].append(rewrite)
    for config_path, rewrites in sorted(rewrites_by_config.items()):
        backup_path = config_path.with_suffix(config_path.suffix + ".bak")
        shutil.copy2(config_path, backup_path)
        backups.append(backup_path)
        config = _read_yaml(config_path)
        for rewrite in rewrites:
            _set_slot(config, rewrite.slot, rewrite.new)
        _atomic_write_yaml(config_path, config)
    return ProfileNormalizationResult(rewrites=plan, changed=True, backups=backups)


def _profile_configs(home: Path) -> list[tuple[Path, dict[str, Any]]]:
    configs = []
    default_config = home / "config.yaml"
    if default_config.is_file():
        configs.append((default_config, _read_yaml(default_config)))
    profiles_dir = home / "profiles"
    if profiles_dir.is_dir():
        for profile_dir in sorted(path for path in profiles_dir.iterdir() if path.is_dir()):
            config_path = profile_dir / "config.yaml"
            if config_path.is_file():
                configs.append((config_path, _read_yaml(config_path)))
    return configs


def _default_profile_combo(home: Path, configs: list[tuple[Path, dict[str, Any]]]) -> str | None:
    default_profile = home / "profiles" / "default" / "config.yaml"
    for path, config in configs:
        if path == default_profile:
            return _main_combo(config)
    return _main_combo(configs[0][1]) if configs else None


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    return data if isinstance(data, dict) else {}


def _main_combo(config: dict[str, Any]) -> str | None:
    model = config.get("model")
    if isinstance(model, dict):
        value = model.get("default")
        return str(value) if value else None
    return str(model) if model else None


def _slot_values(config: dict[str, Any]) -> list[tuple[str, str]]:
    values = []
    main = _main_combo(config)
    if main:
        values.append(("model", main))
    for slot, route in (config.get("auxiliary") or {}).items():
        if not isinstance(route, dict):
            continue
        model = route.get("model")
        if model:
            values.append((f"auxiliary.{slot}", str(model)))
    values.extend(_gateway_slot_values(config))
    return values


def _gateway_slot_values(config: dict[str, Any]) -> list[tuple[str, str]]:
    values = []
    gateway = config.get("gateway") or {}
    if not isinstance(gateway, dict):
        return values
    platforms = gateway.get("platforms") or {}
    if not isinstance(platforms, dict):
        return values
    for platform_name, platform in sorted(platforms.items()):
        if not isinstance(platform, dict):
            continue
        model = platform.get("model")
        if model:
            values.append((f"gateway.platforms.{platform_name}.model", str(model)))
        for slot, route in (platform.get("auxiliary") or {}).items():
            if isinstance(route, dict) and route.get("model"):
                values.append(
                    (
                        f"gateway.platforms.{platform_name}.auxiliary.{slot}",
                        str(route["model"]),
                    )
                )
    return values


def _rewrite_target(
    value: str,
    *,
    existing_combos: set[str],
    combo_by_canonical: dict[str, str],
    default_combo: str | None,
) -> str | None:
    if not value or value == "auto" or value in existing_combos:
        return None
    return combo_by_canonical.get(_canonical(value)) or default_combo


def _combo_by_canonical(current_combos: dict[str, list[str]]) -> dict[str, str]:
    index = {}
    for combo_id, members in current_combos.items():
        if not combo_id.startswith("fmo-"):
            continue
        for member in members:
            index.setdefault(_canonical(member), combo_id)
    return index


def _canonical(model_id: str) -> str:
    return model_id.rsplit("/", maxsplit=1)[-1].lower()


def _set_slot(config: dict[str, Any], slot: str, value: str) -> None:
    if slot == "model":
        model = config.get("model")
        if isinstance(model, dict):
            model["default"] = value
        else:
            config["model"] = value
        return
    parts = slot.split(".")
    if parts[0] == "auxiliary":
        _set_auxiliary_slot(config, parts[1], value)
        return
    platform = config.setdefault("gateway", {}).setdefault("platforms", {}).setdefault(parts[2], {})
    if len(parts) == 4:
        platform["model"] = value
        return
    _set_auxiliary_slot(platform, parts[4], value)


def _set_auxiliary_slot(owner: dict[str, Any], name: str, value: str) -> None:
    owner.setdefault("auxiliary", {}).setdefault(name, {})["model"] = value
    owner["auxiliary"][name]["provider"] = "omniroute"


def _atomic_write_yaml(path: Path, config: dict[str, Any]) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as tmp:
            yaml.safe_dump(config, tmp, sort_keys=False)
        Path(tmp_name).replace(path)
    finally:
        tmp_path = Path(tmp_name)
        if tmp_path.exists():
            tmp_path.unlink()
