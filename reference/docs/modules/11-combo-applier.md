# Модуль 11 — Combo Config Applier

## Цель

Безопасно синхронизировать allocation plan с OmniRoute combo.

## Read current state

Получить combo через management API:

```text
GET /api/combos
GET /api/combos/{id}
```

FMO не использует `/v1/combos`: это public projection, а не operator-owned
management state.

## Desired combo naming

```text
fmo-role-routing-fast
fmo-role-research-scout
...
```

Сервис управляет только combo с prefix `fmo-`.

## Diff

Сравнивать:

- target model IDs;
- order;
- weights;
- fallback policy;
- enabled state.

Нормализовать порядок полей и округление weights.

## Apply transaction

1. advisory lock `combo_apply`;
2. повторно прочитать current state;
3. проверить, что hash не изменился;
4. сохранить snapshot в PostgreSQL;
5. применить update через `PUT /api/combos/{id}`;
6. прочитать combo обратно;
7. сравнить с desired;
8. выполнить smoke test через combo model name;
9. commit change record.

FMO не создаёт и не удаляет combo. Если desired `fmo-*` combo отсутствует в
live set, apply reports `unmanaged_combo` and skips it.

## Smoke test

```text
POST /v1/chat/completions
model = fmo-role-...
X-OmniRoute-No-Cache = true
```

`/api/combos/test` запрещён для FMO smoke path.

Проверить:

- ответ успешен;
- фактический routed endpoint входит в targets, если это видно;
- не использован excluded endpoint;
- latency в пределах hard timeout.

## Rollback

При ошибке:

- восстановить pre-change snapshot;
- повторно прочитать;
- smoke test старой версии;
- пометить run failed.

## Anti-churn

- minimum score improvement;
- minimum weight delta;
- max changes per run;
- cooldown after apply;
- no apply during incomplete telemetry sync.

## Manual protection

Если человек изменил `fmo-` combo вне сервиса:

- detect drift;
- не перетирать автоматически;
- создать conflict;
- требовать `--force` или override policy.
