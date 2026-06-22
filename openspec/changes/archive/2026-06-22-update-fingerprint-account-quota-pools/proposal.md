# Change: Treat provider fingerprints as account quota pools

## Why

OmniRoute provider connections can expose multiple registered upstream accounts
inside one connection as `providerSpecificData.fingerprints`. Today FMO ignores
those fingerprints and models the connection as one shared quota pool, so a
provider with three real accounts is planned as one account instead of three
independent per-account quota pools.

This undercounts safe free capacity and can produce weaker combos than the
available OmniRoute configuration supports.

## What Changes

- Expand OmniRoute provider connections with `providerSpecificData.fingerprints`
  into deterministic virtual provider-account scopes.
- Treat each unique fingerprint as a separate confirmed account quota pool for
  providers whose upstream account quota is per registered account.
- Keep providers without fingerprints on the existing conservative shared-pool
  path.
- Ensure endpoint discovery, quota capacity calculation, and combo allocation
  use the fingerprint account scopes instead of the parent connection alone.

## Impact

- Affected specs: `account-discovery`
- Affected code:
  - `src/fmo/accounts.py`
  - `src/fmo/composition_stages.py`
  - `src/fmo/scanner.py` if endpoint fanout still relies on one account per
    OmniRoute connection
  - allocation tests that verify pool capacity and combo construction
- Affected fixtures/tests:
  - `reference/fixtures/external-responses/omniroute_api_providers.json`
    contains providers with three account fingerprints each and should be used
    as fixture evidence, not as provider-specific branching.
  - executable spec tests must remove the matching
    `account-discovery::*` entries from `tests/spec_coverage_pending.txt`.
