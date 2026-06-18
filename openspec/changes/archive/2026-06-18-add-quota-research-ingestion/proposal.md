# Change: Production quota research ingestion

## Why

Quota research currently relies on injected test doubles. The search/research
client needs to run against configured auth, persistence, retries and structured
extraction in production.

## What Changes

- Wire the quota-research search client to OmniRoute `POST /v1/search`
  (`gemini-grounded-search`) with configured auth, bounded retries and immutable
  snapshot persistence of the `answer.text` source.
- Run structured extraction (Instructor) over the real search result instead of a
  test double; fail conservatively when search is unavailable.
- Record realistic search-response fixtures for deterministic tests of this
  boundary.

## Impact

- Affected specs: `quota-research`
- Affected code (later): `src/fmo/quota_research.py`, `src/fmo/omniroute.py`
- Spec-only proposal; no implementation in this change.
