# add-foundation

## Why

The orchestrator needs its architectural skeleton defined before any feature
slice: what the unit of management is, how the daily batch is bounded, where
state lives, how OmniRoute is reached, and how runs are scheduled and made safe.
This phase distils the cross-cutting architecture from
`reference/docs/architecture/00,01,10` and `reference/docs/modules/01,13`.

## What Changes

- Add `system-architecture`: provider_endpoint as the unit, daily-batch model,
  transaction boundaries, idempotency, endpoint/quota/combo state machines and
  forbidden transitions.
- Add `data-model`: PostgreSQL as the single store (schema + migrations), text
  role ids, the canonical status vocabulary.
- Add `environment-and-connections`: env-only secrets, startup validation,
  prompt secret redaction.
- Add `omniroute-client`: single gateway client, version handshake, read-only on
  unknown version, retry policy.
- Add `scheduler`: daily pipeline order, locks, additional run triggers, and the
  prohibition on `/api/combos/test`.
- Add `llm-runtime`: one uniform Instructor runtime for all four LLM sites, with
  per-site prompts as independently editable external files and no secrets in
  prompts.

## Impact

- New specs: `system-architecture`, `data-model`, `environment-and-connections`,
  `omniroute-client`, `scheduler`, `llm-runtime`.
- Foundation for every later phase (discovery, quota, scoring, allocation,
  lifecycle).
- No runtime-routing behavior (OmniRoute-owned).
