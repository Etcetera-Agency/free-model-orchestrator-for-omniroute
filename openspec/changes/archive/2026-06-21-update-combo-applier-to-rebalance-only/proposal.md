# update-combo-applier-to-rebalance-only

## Why

The operating model is: **the operator creates a combo in OmniRoute by hand and
seeds it with one model; the orchestrator only rebalances the membership of
combos that already exist.** The orchestrator must never create or delete a
combo.

Today the apply stage cannot honor that. `_apply_stage`
(`src/fmo/composition_stages.py`) issues `POST /api/combos/{combo_id}` with the
desired model list for every desired `fmo-` diff. That call is an **upsert**: a
combo id that does not yet exist would be created as a side effect. There is also
no path that distinguishes "combo exists, rebalance it" from "combo referenced
but absent."

The existing `Manage only fmo- combos` requirement scopes mutations to the
`fmo-` prefix but says nothing about creation/deletion. This change tightens the
contract to **rebalance-only**: apply mutates the membership of existing `fmo-`
combos and never materializes a new one. A desired combo that does not exist in
the live OmniRoute set is reported as unmanaged and skipped (the
`add-profile-combo-normalization` slice is what redirects a profile slot away
from a non-existent combo, so apply itself never needs to create one).

This also removes the now-inapplicable "unknown role triggers a full inventory
to create the role" expectation from the inventory spec: because a referenced but
non-existent combo resolves to the default combo instead of being created, the
immediate-create path is not needed.

## What Changes

- Apply SHALL rebalance only combos that exist in the live OmniRoute combo set;
  it SHALL NOT create or delete combos.
- A desired `fmo-` diff whose combo id is absent from the live set SHALL be
  skipped and reported as `unmanaged_combo` (not created), without failing the
  run for the other combos.
- The existing drift, smoke, rollback and "manage only fmo-" guarantees are
  preserved for combos that do exist.
- Remove the unwired "unknown-role immediate full inventory" expectation from the
  `hermes-inventory` `Daily and unknown-role inventory` requirement (the helper
  `should_run_full_inventory` is referenced only by a unit test and is not on any
  runtime path; the default-combo fallback supersedes it).

## Impact

- Modified specs: `combo-applier` (rebalance-only: never create or delete),
  `hermes-inventory` (drop the unknown-role immediate-create expectation).
- Affected code: `src/fmo/composition_stages.py` (`_apply_stage`,
  `_read_current_combos`), `src/fmo/applier.py` (`ComboApplier`).
- Depends on: nothing (independent of the read/enumerate slices).
- Feeds: `add-profile-combo-normalization` (relies on apply never creating).
