# Status: IMPLEMENTED

Quota implemented with TDD in `tests/test_quota.py`.

- Quota research builds date-aware OmniRoute `/v1/search` requests with `gemini-grounded-search` and snapshots `answer.text`.
- Quota claims validate metric/window/positive amount/evidence deterministically.
- Summary rules cap confidence, mark `activated_by=summary`, use opportunistic capacity, and enter safe mode when quota worsens.
- Access classifier follows availability, zero price, quota, promotion, exclusion, trust/fail-closed order.
- Attribution capacity follows confirmed/inferred/assumed_shared/unknown rules and merge/split evidence triggers allocation recalculation.
- Quota manager computes effective remaining, enforces hard stops, fetches live quota before reset reclassification, and rejects historical records lacking reserve.

Verification:

- `.venv/bin/python -m pytest tests/test_quota.py tests/test_discovery.py tests/test_foundation.py -q`
- `/Users/theDay/.nvm/versions/node/v24.1.0/bin/openspec validate add-quota --strict`
