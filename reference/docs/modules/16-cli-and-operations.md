# Модуль 16 — CLI и эксплуатация

## Команды

```bash
free-model-orchestrator sync-free-registry
free-model-orchestrator discover-accounts
free-model-orchestrator scan-providers
free-model-orchestrator research-quotas
free-model-orchestrator classify-access
free-model-orchestrator sync-metadata
free-model-orchestrator match-models
free-model-orchestrator probe-models
free-model-orchestrator sync-telemetry
free-model-orchestrator sync-quotas
free-model-orchestrator score-roles
free-model-orchestrator allocate
free-model-orchestrator diff
free-model-orchestrator apply
free-model-orchestrator rollback
free-model-orchestrator full
```

## Общие flags

```text
--dry-run
--provider
--account
--endpoint
--role
--run-id
--force
--json
--verbose
```

## Диагностика

```bash
... explain-endpoint ENDPOINT_ID
... explain-role research_scout
... show-free-provider PROVIDER
... show-free-pool POOL_KEY
... show-accounts PROVIDER
... show-quota-pool POOL_ID
... show-conflicts
... show-unmatched
... show-drift
```

## Exit codes

```text
0 success
2 partial/stale data
3 validation failed
4 external dependency failed
5 unsafe to apply
6 apply failed and rolled back
7 rollback failed
```


## Artificial Analysis index migration commands

```text
free-model-orchestrator aa-index status
free-model-orchestrator aa-index analyze
free-model-orchestrator aa-index proposal
free-model-orchestrator aa-index approve MIGRATION_ID
free-model-orchestrator aa-index reject MIGRATION_ID
free-model-orchestrator aa-index rollout MIGRATION_ID
free-model-orchestrator aa-index rollback MIGRATION_ID
```
