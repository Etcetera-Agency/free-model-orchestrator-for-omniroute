# Change: Lock the published payload to the OmniRoute ingest contract

## Why

The publisher (`src/fmo/pool_publisher.py::compose_pool_generation`) emits the canonical
`fmo-pools/v1` shape from the concept (§4), but the OmniRoute ingester historically
validated a *different* shape, so a real `PUT /api/fmo/pools` is rejected with `400`.
The OmniRoute side is being aligned to this canonical shape
(`align-fmo-pools-contract-ingest`). This change locks the FMO emitter to that exact
wire contract with a shared golden fixture and a deterministic conformance test, and
closes the two cross-repo ambiguities that would still make gates silently never match
even once the JSON shape lines up:

1. **Capability vocabulary.** The publisher emits `constraints.capabilities` (e.g.
   `["chat", "tools"]`), but OmniRoute matches a candidate's `required_capabilities`
   against capability tokens it derives from the synced model (endpoints, `api:*`,
   `thinking`, compat-override tokens). If the two vocabularies differ, every
   capability gate fails and pools never fill. The publisher SHALL emit tokens drawn
   from the agreed shared vocabulary.
2. **Quality category.** The publisher maps a metric to a `quality_band.category`
   (`intelligence`/`coding`/`agentic`), and OmniRoute resolves the band via
   `getResolvedTaskFitness(model, category)`. The category names SHALL be ones
   OmniRoute's model-intelligence resolver understands.

Idempotency is already payload-hash based on the FMO side (`Idempotency-Key = payload
hash`); the mismatch was OmniRoute requiring `key === generation`, fixed on that side.
No FMO idempotency change is needed — this change only asserts it stays payload-hash.

## What Changes

- `src/fmo/pool_publisher.py` — keep the FMO-owned fields, but emit them against the
  agreed canonical `fmo-pools/v1`: `contract_version`, `demand`
  (`requests_per_day`, `consumers`, `workload_class`), `constraints`
  (`free_only`, `capabilities`, `min_context_tokens` as int, `quality_band` intent with
  `relax: { max_delta, when }`), and `tail` intent (`strategy`, `mode`, `compatibility`).
- Capability emission draws from the shared capability vocabulary; `quality_band.category`
  uses an OmniRoute-recognized category name.
- `tests/` + a shared golden fixture `fmo-pools/v1` example, asserted byte-for-byte
  against a deterministic schema check mirroring the OmniRoute ingester, so the two
  repos cannot drift again silently.

## Impact

- **Capability**: `pool-spec-publisher` (adds "Wire-contract conformance"; the
  FMO-owned-fields and idempotent-publish requirements are unchanged).
- **Reused**: `compose_pool_generation`, `publish_pool_generation`, the payload-hash
  idempotency, `stable_hash`.
- **Net-new**: the shared golden fixture + conformance test; the capability/category
  vocabulary alignment.
- **Pairs with**: OmniRoute `align-fmo-pools-contract-ingest` (same canonical shape and
  fixture). Together they make the seam actually round-trip.
