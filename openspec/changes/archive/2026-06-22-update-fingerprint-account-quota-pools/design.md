# Design: Fingerprint-backed account quota pools

## Context

OmniRoute exposes some providers as a single connection with nested account
fingerprints:

```json
{
  "provider": "example-provider",
  "providerSpecificData": {
    "fingerprints": ["fp-a", "fp-b", "fp-c"]
  }
}
```

For providers with this shape, the fingerprint list represents registered
upstream accounts behind that provider connection. FMO's current grouping only looks at
top-level fields such as `upstream_account_id`, `rate_limit_account_id`,
`credential_fingerprint`, and `manual_pool_key`, so it collapses the nested
accounts into one shared pool.

## Goals

- Count any provider connection with account fingerprints as independent account
  quota scopes when the fingerprint list is the account identity evidence.
- Preserve conservative behavior for providers without fingerprints.
- Deduplicate repeated fingerprints before capacity calculation.
- Make allocation and combo construction see separate quota pools for separate
  fingerprints.

## Non-Goals

- Do not infer account multiplication from model count, connection count, or
  provider name alone.
- Do not treat keyless/no-auth IP or installation scopes as account capacity.
- Do not multiply a live OmniRoute `quotaTotal` when it is connection-wide and
  not proven per fingerprint.

## Decision

Provider connections with non-empty `providerSpecificData.fingerprints` SHALL be
expanded into virtual account-scope records before quota grouping. Each unique
fingerprint gets a stable scope key:

```text
<provider>:fingerprint:<fingerprint>
```

That scope key becomes the quota pool key and provider-account external ref. The
parent OmniRoute connection id remains in metadata for API calls and traceability.

## Pseudocode

```python
def expand_connection_accounts(connection):
    fingerprints = connection["providerSpecificData"].get("fingerprints", [])
    if not fingerprints:
        return [connection]

    accounts = []
    for fingerprint in sorted(set(fingerprints)):
        accounts.append({
            **connection,
            "id": f"{connection['id']}#fingerprint:{fingerprint}",
            "parent_connection_id": connection["id"],
            "credential_fingerprint": fingerprint,
            "manual_pool_key": f"{connection['provider']}:fingerprint:{fingerprint}",
            "status": "confirmed",
            "quota_scope_type": "account_fingerprint",
            "quota_scope_key": fingerprint,
        })
    return accounts
```

The account-discovery stage persists each expanded account as a provider account,
assigns a named quota pool from the fingerprint key, and records membership with
`membership_reason = account-fingerprint`.

Endpoint discovery then fans out provider models across those provider accounts,
so allocation can evaluate one endpoint per account scope while still pointing
back to the same OmniRoute provider connection.

## Risks / Trade-offs

- If OmniRoute later reports a shared counter for a fingerprint-backed provider,
  account discovery must merge those pools back to `assumed_shared` or `unknown`.
- If a provider includes fingerprints for something other than account identity,
  this change would overcount capacity. The slice relies on the structural
  `providerSpecificData.fingerprints` account list and must not special-case
  provider names.

## Rollback

Remove fingerprint expansion and rerun account discovery. Provider accounts fall
back to one quota pool per OmniRoute connection or existing shared pool key.
