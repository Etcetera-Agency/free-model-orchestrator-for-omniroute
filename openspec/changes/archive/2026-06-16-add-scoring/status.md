# Status: IMPLEMENTED

Scoring implemented with TDD in `tests/test_scoring.py`.

- Probe gates require free access and reserved capacity; probes use dedicated provider routes with no-cache and capability-gated suites.
- Probe errors map 402/429/401/403/5xx to exclusion, quota-manager handoff, auth degraded, and retry paths.
- Telemetry records latency granularity honestly and endpoint degradation does not disable sibling providers.
- Eligibility rejects non-free, unprobed, unmatched, open-breaker, insufficient-quota, and missing-capability endpoints before scoring.
- AA scoring normalizes present metrics, redistributes missing metric weights, and marks all-missing quality unknown.
- Scoring excludes price, honors latency source priority, and skips unchanged input hashes.
- Context and quality gates are hard filters with unknown/unverifiable/index-change handling.

Verification:

- `.venv/bin/python -m pytest tests/test_scoring.py tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q`
- `openspec validate add-scoring --strict`
