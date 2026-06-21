# Design — rebalance-only apply

## OmniRoute apply today (verified in code)

`_apply_stage` (`src/fmo/composition_stages.py`):

```python
current = _read_current_combos(client)            # GET live combos -> {id: [models]}
for diff in diffs:
    combo_id   = diff["omniroute_combo_id"]
    diff_before= diff.state_json["before"]
    live       = current.get(combo_id, [])         # [] when combo absent
    desired    = diff.state_json["after"]
    if not combo_id.startswith("fmo-"): continue
    if live != diff_before: return unsafe(combo_drift_detected)
    client.post(f"/api/combos/{combo_id}", {"models": desired}, idempotency_key=hash)  # UPSERT — creates if absent
    smoke = _smoke_combo(client, combo_id)
    ...
```

`POST /api/combos/{id}` is an upsert: when `combo_id` is absent the call would
**create** the combo. There is no "exists?" gate. `_read_current_combos` already
returns the live set, so existence is knowable before the POST.

## Change (pseudocode)

```python
current = _read_current_combos(client)            # source of truth for existence
existing_ids = set(current)
for diff in diffs:
    combo_id = diff["omniroute_combo_id"]
    if not combo_id.startswith("fmo-"):
        continue                                  # foreign combo, untouched (unchanged)
    if combo_id not in existing_ids:
        report_unmanaged(combo_id)                # NEVER create
        continue                                  # skip; other combos still applied
    # --- existing combo: unchanged rebalance path ---
    live = current[combo_id]
    if live != diff.state_json["before"]:
        return unsafe(combo_drift_detected)
    client.post(f"/api/combos/{combo_id}", {"models": desired}, idempotency_key=hash)
    ...                                           # smoke / rollback / persist as today
```

Key points:

- Existence is decided **only** from the live OmniRoute set (`_read_current_combos`),
  never from our DB — the operator may have just created the combo by hand, and a
  combo we know about may have been deleted.
- Skipping an absent combo is **not** a run failure: the remaining diffs are still
  applied. The skipped combo is surfaced as `unmanaged_combo` in stage details so
  the operator (or the normalization slice) can act.
- No DELETE is ever issued. Membership shrinking to empty is out of scope; a combo
  the operator no longer wants is removed by the operator.
- Drift / smoke / rollback / "manage only fmo-" behavior is unchanged for combos
  that exist.

## ComboApplier

`ComboApplier.managed_names()` already filters to `fmo-`. Add an explicit guard so
`apply()` refuses an id not present in its `current` map (defense in depth), and
keep `ComboConflict` for drift.

## Removing the unknown-role immediate-create expectation

`should_run_full_inventory(observed_role, known_roles)` is defined in
`src/fmo/hermes_inventory.py` and referenced **only** by `tests/test_role_lifecycle.py`
— it is on no runtime path. The `hermes-inventory` spec's `Daily and
unknown-role inventory` requirement still promises an immediate full run on an
unknown role. With the default-combo fallback (`add-profile-combo-normalization`),
a slot referencing a non-existent combo resolves to the default combo rather than
forcing creation, so the immediate-create trigger is unnecessary. This slice
removes that expectation from the spec; the daily/manual/event triggers remain.
