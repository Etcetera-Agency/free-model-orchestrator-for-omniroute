# update-hermes-source-to-per-profile-config

## Why

The inventory reads Hermes profiles from `hermes profile list` (the
`ProfileInfo` summary, mirrored by our `profiles.json` fixture). That record
carries only the **main** model slot:

```
ProfileInfo(name, path, is_default, gateway_running, model, provider,
            has_env, skill_count, alias_*, distribution_*, description, ...)
```
(verified upstream: `hermes_cli/profiles.py` `@dataclass ProfileInfo`,
NousResearch/hermes-agent `v2026.6.19`).

There is **no auxiliary information in the profile list at all.** In current
Hermes a profile configures two kinds of model slots
(`website/docs/user-guide/configuring-models.md`):

- one **main** model, and
- an **`auxiliary:`** block of independent task slots (vision, compression,
  title generation, web_extract, approval, mcp, skills, kanban specify/decompose,
  profile describe, curator, plus `tts_audio_tags` / `session_search` in the
  `v2026.6.19` config example).

Those auxiliary slots live **only in each profile's own
`<profile_dir>/config.yaml`** — each profile is an independent config
(`website/docs/user-guide/profiles.md`: "config.yaml — model, provider,
toolsets, all settings"; cloning a profile copies its whole `config.yaml`).

Because `parse_profiles` (`src/fmo/hermes_inventory.py`) reads only
`profile.get("model")` from the list summary, every per-profile auxiliary slot is
invisible to the orchestrator. Since all model slots route through OmniRoute,
auxiliary combos are real free-capacity consumers that are never enumerated.

We are also pinned to Hermes `v2026.6.5`; the latest tag is `v2026.6.19`
(`ORACLE_FRESH_SERVER_DEPLOY.md` install line).

This change is the **foundation**: switch the profile source from the list
summary to each profile's `config.yaml`, so the auxiliary slots become available
to later slices. It does not yet emit auxiliary consumers (that is
`add-auxiliary-slot-consumers`).

## What Changes

- Read each profile's `<path>/config.yaml` (the `path` comes from the existing
  profile-list / `ProfileInfo` record) and expose both `model` and the
  `auxiliary` mapping to the parser, instead of relying on the list summary's
  `model` field alone.
- Keep the existing list enumeration only to discover profile names, paths and
  `gateway_running` (consumer-type selection is unchanged here).
- Record real `v2026.6.19` fixtures: a `config.yaml` per profile, at least one
  with a non-empty `auxiliary:` block (an explicit override and an `auto` slot),
  and bump the documented pin to `v2026.6.19`.

## Impact

- Modified specs: `hermes-inventory` (new requirement: model slots are read from
  per-profile `config.yaml`, not from the list summary).
- Affected code: `src/fmo/hermes_inventory.py` (profile reading: `read_hermes_home`
  / `enumerate_live_profiles` / `parse_profiles` source), fixtures under
  `tests/_fixtures/hermes/`.
- Depends on: nothing.
- Feeds: `add-auxiliary-slot-consumers`, `add-profile-combo-normalization`.
