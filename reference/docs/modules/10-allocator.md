# Модуль 10 — Allocator

## Цель

Глобально распределить бесплатную ёмкость всех quota pools между всеми ролями, а затем сформировать для каждой роли устойчивый combo.

Combo не строятся независимо друг от друга.

## Входы

- latest role scores;
- quota pool usable capacity;
- independent quota pool count per provider;
- account independence confidence;
- provider groups;
- historical и projected role load;
- minimum role budgets;
- current combos;
- hard constraints;
- role criticality;
- уже выделенные role quota budgets.

## Hard constraints

```text
free access only
probe passed
quota sufficient
no quota pool oversubscription
max heavy roles per quota pool
max total roles per quota pool
max primary roles per provider group
minimum independent quota pools in top N
minimum independent provider groups in top N
```

Особое правило:

```text
research_scout
health_reasoning
cross_domain_orchestrator
```

не могут одновременно иметь primary в одном quota pool.

## Optimization

### Этап 1. Рассчитать спрос ролей

Для каждой роли и quota reset horizon:

```text
expected_requests
protected_requests
expected_input_tokens
protected_input_tokens
expected_output_tokens
protected_output_tokens
peak_concurrency
minimum_guaranteed_capacity
```

Расчёт выполняется после суммирования всех agent-role bindings и раскрытия shared-role dependencies.

Источники:

1. observed executions and role calls;
2. configured agent schedule;
3. configured calls per agent run;
4. shared-role dependency rules;
5. conservative bootstrap estimate.

### Этап 2. Рассчитать usable quota pools

Для каждого pool:

```text
confirmed capacity
- safety reserve
- probe reserve
= usable capacity
```

### Этап 3. Выделить role quota budgets

Сначала минимальный гарантированный бюджет получают критичные роли.

Затем остаток распределяется по:

```text
criticality × expected demand × lack of alternatives
```

Результат сохраняется до формирования combo.

### Этап 4. Назначить primary endpoint

Primary должен иметь не только высокий score, но и выделенный этой роли budget в соответствующем quota pool.

Тяжёлые роли по возможности получают разные основные quota pools.

### Этап 5. Построить расширенный combo

Рекомендуемые настройки:

```text
target_combo_size: 8–15 endpoint
minimum_combo_size: 4 endpoint
maximum_per_quota_pool: 2
maximum_per_provider_group: 3
```

Но endpoint добавляется только если он:

- имеет guaranteed budget для роли; либо
- добавляется как opportunistic fallback с ограниченным весом.

### Этап 6. Рассчитать weights

Для guaranteed endpoint:

```text
weight ∝ role_score × allocated_capacity
```

Для opportunistic fallback:

```text
weight <= opportunistic_max_weight
```

Суммарный projected usage всех ролей по pool не должен превышать usable capacity.

### Этап 7. Global validation

Для каждого quota pool:

```text
sum(guaranteed usage)
+ expected opportunistic usage
<= usable capacity
```

### Этап 8. Backtracking

Если allocation блокирует критичную роль или создаёт oversubscription:

1. убрать shared endpoint у менее критичной роли;
2. уменьшить opportunistic weights;
3. заменить provider;
4. сократить combo;
5. пометить роль degraded.

## Degraded modes

### Нет primary

```text
role_status = unavailable
```

### Один endpoint

```text
role_status = degraded_single_provider
```

### Недостаточно quota

```text
role_status = degraded_low_quota
```

Платный fallback не создаётся.

## Stability

Daily run не должен перестраивать порядок без существенной причины.

Не менять combo, если:

- набор eligible endpoint не изменился;
- score movement не пересёк reorder threshold;
- improvement меньше threshold;
- новый endpoint ещё не прошёл stability period;
- текущий большой combo остаётся достаточным.

## Результат

### Global allocation plan

```text
quota_pool_id
usable_capacity
reserved_by_role
opportunistic_by_role
unallocated_reserve
oversubscription_ratio
```

### Role allocation plan

```text
plan_id
role_id
status
targets_json
quota_budgets_json
constraint_report_json
input_state_hash
created_at
```

План нельзя применить, если хотя бы один quota pool имеет `oversubscription_ratio > 1`.


## Web-cookie allocation rules

Web-cookie endpoint:

- не считается guaranteed capacity при неизвестной quota;
- добавляется как opportunistic fallback;
- получает ограниченный weight;
- не используется в ролях с несовместимыми required capabilities;
- не становится primary без explicit override.


## Context-aware allocation

До quota allocation применяется hard filter:

```text
effective_context_window >= role.minimum_context_window
effective_max_output_tokens >= role.minimum_output_tokens
```

После фильтра все подходящие endpoint участвуют в одном combo роли.

Дополнительная группировка по context size не выполняется. Endpoint с 64K, 128K, 256K и 1M могут находиться в одном combo, если minimum роли равен 64K.

Context window не влияет на quota distribution после прохождения minimum.


## Quality-gate eligibility

Allocator получает только endpoint, прошедшие `minimum_quality_gate` роли.

Если после gate осталось меньше `minimum_combo_size`:

```text
role_status = degraded_quality_capacity
```

Gate не ослабляется автоматически. Изменить threshold можно только через конфигурацию или explicit override.


## Frequency-aware allocation

Количество агентов само по себе не является demand.

Demand определяется:

```text
agent runs × calls per run × token profile
```

Weekly/monthly agents проектируются по конкретным будущим запускам до reset.

Если одна роль используется несколькими агентами, их forecast суммируется до распределения quota.

Если shared role вызывается другими ролями, dependency demand раскрывается до global validation.

Allocation plan обязан содержать demand breakdown по consumer agents и shared dependencies.


## Allocation with uncertain quota attribution

Allocator не предполагает, что каждый endpoint имеет известный независимый pool.

Перед capacity validation endpoints группируются через quota attribution.

```text
confirmed independent groups
+ discounted inferred capacity
+ opportunistic unknown endpoints
```

Guaranteed plan должен оставаться feasible даже при консервативном предположении, что все `assumed_shared` connections одного provider используют одну квоту.

Unknown endpoints могут присутствовать в combo как low-weight fallback, но не закрывают minimum guaranteed demand.


## Cold-start demand handling

Allocator receives `demand_source`:

```text
observed
blended
configured
bootstrap
bootstrap_unknown
```

Priority for guaranteed capacity:

```text
protected observed/blended demand
protected configured/bootstrap demand
```

`bootstrap_unknown` is valid but must be marked low-confidence and receive the configured cold-start safety multiplier.

Historical values must already include the 20% reserve exactly once.


## Combo output format

Allocator emits ordered endpoint lists using:

```text
strategy = priority
```

No endpoint weights are calculated or stored.

The order is the routing policy:

```text
index 0 = primary
index 1..N = fallback sequence
```

After deterministic validation the optional Smart Combo Reviewer may propose only add/remove/move operations.


## Dynamic roles

Allocator receives the current reconciled active role set rather than a fixed hard-coded list.

New roles use cold-start demand and an existing role policy template.

Roles in `retiring` keep their current combo but do not receive speculative capacity expansion.
