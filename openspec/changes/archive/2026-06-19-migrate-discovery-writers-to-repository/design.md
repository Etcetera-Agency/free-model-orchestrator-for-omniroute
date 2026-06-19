## Context

Repository methods already cover much of the data model, but discovery and
registry paths still open direct psycopg connections and embed SQL. That violates
the persistence spec and leaves transaction ownership split across modules.

## Goals

- Scanner and registry persistence use repository methods only.
- Stage modules do not embed schema SQL for provider/account/catalog/free-model
  writes.
- Existing idempotency and content-hash behavior stay intact.
- Tests catch direct SQL regressions.

## Non-Goals

- Change the DB schema.
- Change external OmniRoute payload parsing.
- Keep old direct-SQL compatibility wrappers.

## Decisions

- Repository owns table SQL.
- Domain modules may parse payloads and build records, but all writes go through
  repository methods.
- Scanner/registry APIs accept a repository-backed dependency where production
  composition can pass the current repository.

## Pseudocode

```python
class ProviderCatalogRepository:
    def store_snapshot(connection, provider_id, catalog, fetch_status):
        catalog_hash = stable_hash(catalog)
        previous = select_latest_success_hash(connection, provider_id)
        insert_snapshot_on_conflict_do_nothing(connection, provider_id, catalog_hash, catalog)
        return StoredSnapshot(catalog_hash, previous == catalog_hash)

class FreeRegistryRepository:
    def store_outcome(connection, outcome):
        snapshot_id = insert_registry_snapshot(connection, outcome.hashes, outcome.raw_json)
        for model in outcome.free_models_payload["models"]:
            if model["authType"] == "web_cookie":
                continue
            upsert_free_model_definition(connection, model, snapshot_id)
        return snapshot_id

def scan_live_omniroute_catalogs(scanner, client, omniroute_instance_id):
    provider_accounts = fetch_provider_accounts(client)
    with scanner.repository.database.transaction() as tx:
        provider_ids = scanner.upsert_provider_accounts(tx, provider_accounts)
        catalogs = fetch_models_catalogs(client)
        for provider in provider_ids:
            scanner.repository.provider_catalogs.store_snapshot(tx, ...)
            scanner.repository.provider_endpoints.upsert(tx, ...)
```

## Risks / Mitigations

- Risk: refactor changes transaction timing.
  Mitigation: assert rollback and idempotency with DB-backed tests.
- Risk: tests only grep source and miss runtime behavior.
  Mitigation: combine source regression checks with round-trip repository tests.

## Migration Plan

1. Add repository methods and failing tests first.
2. Refactor scanner writes to repository methods.
3. Refactor registry writes to repository methods.
4. Remove direct psycopg connection ownership from scanner/registry write paths.
5. Update `openspec/TODO.md` and `completion.review`.
