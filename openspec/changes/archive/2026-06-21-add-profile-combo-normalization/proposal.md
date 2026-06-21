# add-profile-combo-normalization

## Why

Every Hermes model slot must route through an OmniRoute combo, not a raw
provider/model, so the orchestrator can keep it filled with free capacity. Two
non-conforming cases occur in profile `config.yaml` files:

1. A slot points at a **raw** `provider/model` (e.g. `vision:
   google/gemini-2.5-flash`).
2. A slot points at a **combo id that does not exist** in OmniRoute.

Because the orchestrator never creates combos
(`update-combo-applier-to-rebalance-only`), normalization must rewrite such slots
to an existing combo rather than materialize a new one. The rule the operator
chose:

- Map the slot to the existing combo that **contains the same canonical model**
  (provider-independent) — that combo is built around AA-equivalents of that
  model, which is exactly how combos are constructed.
- If no existing combo contains that canonical model, point the slot at the
  **default combo = the main combo of the `default` profile** (the primary
  agent), never at another profile's combo by accident.

This is a `config.yaml` write, so it is an explicit, opt-in command (separate
from the read-only daily inventory) with dry-run and a backup of each file.

## What Changes

- Add a `normalize-profiles` CLI command that scans every profile's `config.yaml`
  (main + auxiliary + gateway/platform auxiliary) and rewrites non-conforming
  slots:
  - raw `provider/model` or non-existent combo id ⇒ existing combo whose members
    include the slot's canonical model (matched via `matcher`, provider-stripped);
  - else ⇒ the `default` profile's main combo (the default combo).
- A slot already pointing at an existing `fmo-` combo is left unchanged. A slot on
  `auto`/empty is left unchanged (it uses the main combo).
- Support `--dry-run` (report planned rewrites, write nothing) and, on apply,
  back up each `config.yaml` before an atomic rewrite.

## Impact

- New capability spec: `profile-normalization`.
- Modified specs: `cli-and-operations` (new `normalize-profiles` command in the
  surface).
- Affected code: new `src/fmo/profile_normalization.py`, `src/fmo/cli.py`
  (command dispatch), reuse of `src/fmo/matcher.py` (canonical match) and the
  live OmniRoute combo set.
- Depends on: `update-hermes-source-to-per-profile-config` (per-profile read),
  `update-combo-applier-to-rebalance-only` (no creation), and the canonical-model
  combo lookup informed by `add-forecast-driven-quality-band`.
