
# Глобальное распределение квот между ролями

## Проблема

Если независимо создать по 8–15 моделей для каждой роли, одна и та же модель или provider account может попасть сразу во все combo.

Формально combo будут разнообразными, но фактически несколько ролей начнут расходовать одну общую бесплатную квоту.

Поэтому allocation выполняется глобально по всем ролям.

## Предусловие

Перед allocation должны завершиться:

1. Free Provider Registry Sync;
2. Account Discovery;
3. effective quota pool merge.

Allocator получает:

- built-in no-auth pools;
- credential account pools;
- shared `poolKey` groups;
- подтверждённые independent pools.

Число connections или моделей само по себе capacity не создаёт.

## Основные сущности

### Quota pool capacity

```text
quota_pool
usable_requests_until_reset
usable_tokens_until_reset
usable_concurrency
```

### Role demand

Role demand агрегируется из agent usage profiles и shared-role dependencies.

Для каждой роли и quota reset horizon:

```text
expected_requests
protected_requests
expected_input_tokens
protected_input_tokens
expected_output_tokens
protected_output_tokens
peak_concurrency
consumer_agents
criticality
```

### Role quota budget

Доля quota pool, разрешённая конкретной роли:

```text
quota_pool_id
role_id
reserved_requests
reserved_tokens
maximum_share
priority
```

## Алгоритм

### 1. Рассчитать usable capacity

```text
usable_capacity =
confirmed_free_capacity
- safety_reserve
- probe_reserve
- already_committed_capacity
```

### 2. Рассчитать demand ролей

Demand строится из:

- расписаний и event rate каждого агента;
- количества role calls на один agent run;
- token usage на role call;
- shared-role dependencies;
- maintenance workloads;
- historical usage.

Для cron/weekly/monthly jobs считаются конкретные запуски до reset quota pool. Если истории нет, используются configured или conservative bootstrap defaults.

### 3. Распределить scarce pools

Quota pools сортируются по редкости:

```text
мало альтернативных providers
низкая capacity
высокое качество моделей
```

Роли сортируются по:

```text
criticality
demand
число альтернатив
```

Сначала выделяются минимальные бюджеты критичным ролям.

### 4. Назначить primary capacity

Один quota pool не должен быть основным источником capacity для нескольких тяжёлых ролей.

По умолчанию:

```text
max_heavy_roles_per_quota_pool: 1
max_total_roles_per_quota_pool: 3
```

### 5. Добавить shared fallback

Один endpoint может находиться в нескольких combo как дальний fallback, если:

- его суммарный ожидаемый traffic остаётся ниже capacity;
- для каждой роли установлен маленький weight;
- он не считается гарантированной capacity сразу для всех ролей.

### 6. Проверить oversubscription

Для каждого quota pool:

```text
sum(projected_role_usage) <= usable_capacity
```

Если условие нарушено:

1. уменьшить weights;
2. заменить endpoint в менее критичной роли;
3. убрать endpoint из части combo;
4. перевести роль в degraded mode.

## Guaranteed и opportunistic capacity

### Guaranteed

Capacity резервируется за ролью и учитывается при планировании.

### Opportunistic

Endpoint присутствует как дальний fallback без гарантии. Он используется только если primary/fallback выше недоступны.

Opportunistic capacity не должна учитываться как полноценная capacity нескольких ролей.

## Пример

```text
Google quota pool: 1000 requests/day

research_scout: 450 guaranteed
cross_domain_orchestrator: 250 guaranteed
routing_fast: 100 guaranteed
other roles: 100 shared opportunistic
reserve: 100
```

Нельзя назначить каждой роли по 500 requests только потому, что один и тот же endpoint включён в разные combo.

## Проверка результата

Allocation plan обязан содержать:

```text
quota_pool_capacity
reserved_by_role
opportunistic_by_role
unallocated_reserve
oversubscription_ratio
```

План с `oversubscription_ratio > 1` не применяется.


## Agent and shared-role expansion

Перед allocation обязательно выполнить:

```text
agent schedules
→ direct agent-role demand
→ role dependency expansion
→ aggregate role demand
```

Один role combo обслуживает всех агентов этой роли, поэтому его budget должен покрывать суммарную нагрузку.

Общие роли вроде fetch получают demand после dependency expansion и не должны оставаться скрытым неучтённым расходом.

## Demand levels

Guaranteed budgets ориентируются на:

```text
protected demand
```

Opportunistic budgets могут учитывать:

```text
expected demand × expected-use coefficient
```

Oversubscription проверяется после полного раскрытия shared dependencies.


## Quota knowledge classes

Global allocation использует не только `quota_pool`, но и `quota_attribution_group`.

Capacity считается по status:

```text
confirmed independent
confirmed shared
inferred
assumed_shared
unknown
```

Несколько аккаунтов/соединений не увеличивают guaranteed capacity без подтверждения независимого quota counter.

Providers, обнаруженные через открытые источники, участвуют на тех же условиях: official documentation может создать confirmed shared/account/IP scope, а отсутствие данных приводит к conservative grouping.


## Demand safety reserve

Historical demand enters allocation only after:

```text
historical demand × 1.20
```

Protected demand is the maximum of reserved history, historical P95, exact schedule projection, and configured minimum.

During cold start, allocation uses protected bootstrap demand. Enabled roles must not receive zero forecast solely because telemetry is absent.
