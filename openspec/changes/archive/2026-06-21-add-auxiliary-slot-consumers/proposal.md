# add-auxiliary-slot-consumers

## Why

With `update-hermes-source-to-per-profile-config` the inventory can see each
profile's `auxiliary:` block, but it still emits only one consumer per profile
(the main combo). Every auxiliary task slot that points at its own OmniRoute
combo is a real free-capacity consumer that is currently uncounted:

- Its combo is never enumerated, so scoring/allocation never keep it filled with
  free endpoints, and the slot can silently fall to paid/exhausted capacity.
- Its load is never attributed, so the demand for a shared combo is understated.

All slots route through OmniRoute in this deployment, so auxiliary combos must be
first-class consumers. Several auxiliary tasks (vision, compression,
web_extract) are the most call-heavy side-jobs.

Combos are shared by reference: any number of profiles/slots may point at the
same combo id, and their demand sums (the `Consumer registry` requirement and
`reference/README.md` already state that multiple consumers can share one role
combo). So enumeration is per (profile, slot) → combo, and demand aggregates per
combo.

## What Changes

- Emit a `Consumer` for the main slot **and** for each non-`auto` `auxiliary.<slot>`
  in every profile, plus auxiliary overrides set at the gateway/platform level.
- Treat a slot as `auto` (and therefore **not** a separate consumer) when its
  `provider` is `auto` or its `model` is empty — that slot falls back to the
  profile's main combo and is already covered by the main consumer.
- Tag auxiliary consumers with a distinct `consumer_type` (`auxiliary`) and a
  `consumer` key of `f"{profile}:{slot}"`; carry the slot name so capability can
  be derived later.
- Aggregate demand per combo across all referencing slots/profiles so a shared
  combo's forecast reflects total load.

## Impact

- Modified specs: `hermes-inventory` (auxiliary slots are consumers),
  `demand-forecast` (shared-combo demand sums across slots).
- Affected code: `src/fmo/hermes_inventory.py` (`parse_profiles`,
  `parse_gateway_services`, `Consumer` emission), `src/fmo/forecast.py`
  (aggregation already sums by role; verify auxiliary consumers feed it).
- Depends on: `update-hermes-source-to-per-profile-config`.
- Feeds: `add-forecast-driven-quality-band` (capability + demand per combo),
  `add-profile-combo-normalization`.
