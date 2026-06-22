# Design — per-profile config as the model-slot source

## Why a design note

The exact Hermes shapes matter and were verified against upstream
`NousResearch/hermes-agent@v2026.6.19`. This note pins them so the parser is
written against real structures, not a guessed schema.

## Hermes facts (verified upstream)

- `hermes profile list` → `ProfileInfo` (`hermes_cli/profiles.py`). Fields:
  `name, path, is_default, gateway_running, model, provider, has_env,
  skill_count, alias_*, distribution_*, description, description_auto`.
  **No `auxiliary`.** `model` here is the main combo only.
- Each profile is a full config tree at `path` (default profile path, others at
  `~/.hermes/profiles/<name>/`). Slots live in `<path>/config.yaml`:

```yaml
# <profile>/config.yaml
model:                       # main slot — a mapping once configured…
  provider: omniroute
  default: fmo-opus          # the OmniRoute combo id (== role key)
  base_url: ''
  api_mode: chat_completions
# …or the empty-string sentinel "" on a brand-new install (not yet configured).

auxiliary:                   # 0..N task slots, each independent
  vision:
    provider: omniroute
    model: fmo-gemini-flash  # combo id; "" + provider auto => use main
  compression:
    provider: auto
    model: ''                # auto: falls back to the main combo
```

- `model:` may be the **empty-string sentinel** `""` on a fresh profile, or a
  **mapping** with `default` after `hermes setup`/`hermes model`
  (`configuring-models.md`). The reader must handle both.
- The main combo id is `model.default` (mapping) — not `model` itself — once
  upgraded; legacy/string form is the bare combo id.

## Reader shape (pseudocode)

```python
def read_profile_slots(profile_info) -> ProfileSlots:
    cfg = load_yaml(Path(profile_info["path"]) / "config.yaml")

    # main slot: mapping {provider, default, ...} OR sentinel "" OR legacy str
    main = cfg.get("model")
    if isinstance(main, dict):
        main_combo = main.get("default") or None        # combo id or None
    elif isinstance(main, str) and main:
        main_combo = main                                # legacy bare id
    else:
        main_combo = None                                # "" sentinel / unset

    aux = cfg.get("auxiliary") or {}                     # {slot: {provider, model, ...}}
    return ProfileSlots(
        name=profile_info["name"],
        path=profile_info["path"],
        gateway_running=bool(profile_info.get("gateway_running")),
        main_combo=main_combo,
        auxiliary=aux,                                   # raw, parsed by slice 2
    )
```

This slice only *exposes* `main_combo` + `auxiliary`. `parse_profiles` keeps
emitting the single main consumer exactly as today (using `main_combo` instead of
the list-summary `model`). Auxiliary slots are carried through untouched for
`add-auxiliary-slot-consumers` to consume.

## Source selection

`enumerate_live_profiles` still calls the list to get `(name, path,
gateway_running)`. The new per-profile read is layered on top — it does **not**
replace profile discovery, only the slot source. Filesystem/command/http
inventory modes already point at a Hermes home, so `config.yaml` is reachable by
joining `path`.

## Fixtures

Record under `tests/_fixtures/hermes/`:

- `profiles.json` — unchanged list summary (already present), used only for
  name/path/gateway.
- `config.default.yaml` — main `model:` mapping pointing at a combo, **no**
  `auxiliary` (proves back-compat).
- `config.research.yaml` — main mapping + an `auxiliary:` block with one explicit
  override (`vision → fmo-…`) and one `auto` slot (`compression`), to exercise
  both branches in slice 2.
- `config.fresh.yaml` — `model: ""` sentinel, to prove the reader tolerates an
  unconfigured profile.
