# State machines

## Provider endpoint lifecycle

```text
discovered
  ↓
access_pending
  ├─→ excluded_paid
  ├─→ excluded_unknown
  └─→ free_candidate
          ↓
      probe_pending
          ├─→ probe_failed
          └─→ active
                  ├─→ degraded
                  ├─→ quota_exhausted
                  ├─→ removed
                  └─→ active
```

## Quota rule lifecycle

```text
discovered
  ↓
parsed
  ↓
validated
  ├─→ conflicting
  ├─→ rejected
  └─→ active
          ├─→ stale
          ├─→ superseded
          └─→ active
```

## Combo change lifecycle

```text
planned
  ↓
validated
  ↓
snapshot_saved
  ↓
applied
  ├─→ smoke_failed → rolled_back
  └─→ smoke_passed → committed
```

## Запрещённые переходы

- `excluded_unknown → active` без нового подтверждённого quota rule.
- `quota_exhausted → active` до reset и quota refresh.
- `probe_failed → active` без нового успешного probe.
- `planned → applied` без snapshot.
