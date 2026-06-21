# Design — profile → combo normalization

## Inputs (verified)

- Per-profile slots from `update-hermes-source-to-per-profile-config`:
  `main` (`model.default`) + `auxiliary.<slot>` (`{provider, model}`), plus
  gateway/platform auxiliary.
- Live OmniRoute combo set with members: `_read_current_combos(client)` →
  `{combo_id: [provider_model_ids]}`.
- Canonical mapping: `matcher` (`src/fmo/matcher.py`) — `_normalize` strips the
  provider prefix and lowercases (`google/gemini-2.5-flash` → `gemini-2.5-flash`),
  `match_model` resolves a provider model to a canonical slug. Provider is
  irrelevant by design.
- Default combo: the `default` profile's `main` combo (`config.yaml`
  `model.default` of the profile whose `is_default` is true).

## Slot classification (pseudocode)

```python
def classify_slot(value, *, existing_combo_ids):
    # value is the raw slot route: combo id, or provider/model, or "" / auto
    if value in (None, "") or is_auto(value):
        return Keep()                                  # uses main combo
    if value in existing_combo_ids:
        return Keep()                                  # already a live combo
    return Rewrite(canonical=_normalize(value))        # raw model OR dead combo id
```

Note: a dead combo id and a raw model are handled the same way — both resolve via
the canonical model. A combo id that is not a real model id simply won't match
any combo's members, so it falls through to the default combo.

## Target resolution (pseudocode)

```python
def resolve_target(canonical, *, combos_by_canonical, default_combo):
    # combos_by_canonical: {canonical_slug: combo_id} built from live combo members
    hit = combos_by_canonical.get(canonical)
    return hit if hit is not None else default_combo

def build_combos_by_canonical(current_combos):
    index = {}
    for combo_id, members in current_combos.items():
        if not combo_id.startswith("fmo-"):
            continue
        for member in members:
            index.setdefault(_normalize(member), combo_id)   # first combo wins; report collisions
    return index
```

## Write with backup (pseudocode)

```python
def normalize_profiles(profiles, *, client, dry_run):
    current   = _read_current_combos(client)
    existing  = set(current)
    by_canon  = build_combos_by_canonical(current)
    default_c = default_profile_main_combo(profiles)
    plan = []
    for p in profiles:
        for slot, value in iter_slots(p):              # main + auxiliary + gateway aux
            decision = classify_slot(value, existing_combo_ids=existing)
            if isinstance(decision, Rewrite):
                target = resolve_target(decision.canonical, combos_by_canonical=by_canon,
                                        default_combo=default_c)
                plan.append((p, slot, value, target))
    if dry_run:
        return Report(plan, wrote=False)               # nothing touched

    for p in {entry[0] for entry in plan}:
        backup(p.config_path)                          # e.g. config.yaml -> bak/config.yaml.<ts>
    for (p, slot, _old, target) in plan:
        atomically_set_slot(p.config_path, slot, combo=target)  # write temp + os.replace
    return Report(plan, wrote=True)
```

Backup convention follows the operator's "back up before changing a deployed
config" rule: copy each `config.yaml` to a timestamped backup directory before
the first write; rewrite via temp-file + atomic replace so a crash never leaves a
half-written config.

## Boundary

This command writes Hermes config; it is the **only** place the orchestrator
mutates Hermes. It never creates or edits OmniRoute combos — it only points slots
at combos that already exist (or the default). The daily read-only inventory is
unchanged.
