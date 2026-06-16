# Модуль 12 — Audit, Snapshots и Rollback

## Цель

Объяснить каждое решение и восстановить предыдущее состояние.

## Sync run

Каждая команда создаёт `sync_runs`:

```text
id
run_type
started_at
finished_at
status
code_version
config_hash
omniroute_version
trigger
```

## Change event

Для каждого изменения:

```text
entity_type
entity_id
action
before_json
after_json
reason_codes
source_refs
run_id
created_at
```

## Snapshot types

- provider catalog;
- quota source;
- quota rule;
- access state;
- role scores;
- allocation plan;
- OmniRoute combo before/after.

## Explainability

Для назначения endpoint на роль хранить:

```text
why_selected
why_not_next_candidate
quota impact
diversity impact
score components
constraints checked
```

## Rollback scopes

- один combo;
- все combo одного run;
- active quota rule;
- model match.

Catalog snapshots не откатываются, потому что отражают наблюдение.

## Retention

- raw API observations: 30 дней;
- source snapshots: бессрочно или object storage;
- quota rules/change log: бессрочно;
- request-level telemetry: согласно объёму;
- aggregates: бессрочно.
