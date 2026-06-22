# Change: Allow combo management through the live API bridge

## Why

FMO combo apply needs OmniRoute management combo read/write. The live OmniRoute
API bridge at `127.0.0.1:20129` currently serves OpenAI-compatible routes and
FMO read routes, but returns a bridge-level `404` for `/api/combos*`.

That blocks production apply before OmniRoute's own management auth or combo
handler can run. The required route already exists in OmniRoute
(`src/app/api/combos/route.ts`) and is protected by `requireManagementAuth`.
FMO must use that management surface, not a projected public `/v1/combos`
endpoint.

## What Changes

- The live API bridge SHALL forward the management combo routes FMO needs:
  `GET /api/combos` and existing-combo read/write routes under
  `/api/combos/{id}`.
- Bridge-level route policy SHALL stop returning `404` for allowed management
  combo paths; missing/invalid management credentials SHALL reach OmniRoute and
  fail as auth errors, not masquerade as missing routes.
- FMO combo apply SHALL read and mutate live combos through the shared
  OmniRoute client pointed at the live API bridge.
- FMO SHALL NOT use `/v1/combos` or any projected public combo endpoint for
  management apply.
- The forbidden helper route `/api/combos/test` remains forbidden.
- Live verification and docs SHALL record the bridge behavior before and after
  the slice.

## Impact

- Affected specs: `omniroute-client`, `combo-applier`.
- Affected implementation after approval:
  - bridge route allowlist/policy for `127.0.0.1:20129`;
  - FMO OmniRoute client/apply path tests that cover management combo
    read/write through the bridge;
  - docs/playbook notes that describe live verification of `/api/combos*`.
- Not in scope for this proposal:
  - code or fixture changes during proposal creation;
  - public `/v1/combos` projection work;
  - `/api/combos/test` enablement.
