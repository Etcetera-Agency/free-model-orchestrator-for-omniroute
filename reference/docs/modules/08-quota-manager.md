# Модуль 08 — Quota Manager

## Цель

Объединить quota rule и фактический usage, чтобы гарантировать отсутствие платного списания.

## Входы

- active quota rule;
- `/api/rate-limits`;
- provider adapter live quota;
- OmniRoute usage;
- локальные counters;
- pending requests;
- reset policy;
- quota pool membership.

## Quota pool

Несколько endpoint могут делить один лимит.

Пример:

```text
antigravity account A
agy account A
```

Если они используют общий upstream account, оба привязываются к одному `quota_pool`.

## Counter model

Для каждого metric:

```text
limit
reported_used
local_used_since_observation
pending_reserved
safety_buffer
effective_remaining
```

Формула:

```text
effective_remaining =
min(
  provider_reported_remaining,
  limit - locally_observed_usage
)
- pending_reserved
- safety_buffer
```

Если одного значения нет, используется только надёжное. Если нет ни одного — endpoint excluded.

## Reservation

Orchestrator резервирует quota только для собственных probe.

Production traffic проходит через OmniRoute и не требует отдельной reservation на каждый запрос со стороны orchestrator.

Для daily allocation используется прогноз доступной ёмкости до следующего reset. Combo содержит много моделей, поэтому краткосрочное исчерпание одной квоты должно обрабатываться fallback-механизмом OmniRoute.

## Safety buffer

Поддержать:

- процент;
- абсолютный минимум requests;
- абсолютный минимум tokens;
- telemetry lag multiplier.

## Reset

Reset calculator поддерживает:

```text
fixed UTC timestamp
calendar day timezone
rolling window
provider-reported timestamp
manual
```

После reset:

1. не обнулять blindly;
2. запросить live quota;
3. обновить counters;
4. reclassify access;
5. разрешить probe.


## Role quota budgets

Quota Manager передаёт Allocator не просто общий remaining, а доступную ёмкость для распределения по ролям.

Хранить:

```text
quota_pool_id
role_id
budget_type = guaranteed|opportunistic
requests_budget
tokens_budget
valid_until
allocation_plan_id
```

Guaranteed budget нельзя одновременно обещать другой роли.

Opportunistic budget может пересекаться, но:

- имеет маленький maximum weight;
- не считается гарантией доступности;
- учитывается через expected-use coefficient.

Для тяжёлых ролей:

```text
research_scout
health_reasoning
cross_domain_orchestrator
```

по умолчанию запрещено использовать один quota pool как основной guaranteed budget более чем для одной роли.

## Forecast

Для каждой роли оценить расход:

```text
requests/hour
tokens/request
peak multiplier
```

Прогноз:

```text
hours_to_exhaustion
projected_usage_until_reset
```

Allocator не назначает primary, если projected usage превышает usable quota.

## 429 vs quota exhaustion

429 может означать краткосрочный RPM, а не конец бесплатной квоты.

Normalize по:

- headers;
- body;
- quota rule;
- reset time.

## Hard stop

Если provider/OmniRoute умеет самостоятельно останавливать запросы после исчерпания free quota, endpoint может оставаться в большом combo и временно выпадать через runtime fallback.

Если hard stop не гарантирован, endpoint не допускается в combo вообще.

Daily batch исключает endpoint, у которого к моменту расчёта квота уже исчерпана или правило стало недействительным.


## Demand forecast input

Quota Manager получает forecast из модуля Agent and Role Demand Forecast.

Для каждого quota pool forecast пересчитывается до его собственного reset:

```text
expected role demand
protected role demand
shared-role demand
maintenance demand
```

Quota Manager не использует фиксированный `requests/day`, если известны cron schedules или weekly/monthly bursts.

Guaranteed budgets должны покрывать protected demand с учётом safety reserve.

Если quota ограничена одновременно requests и tokens, проверяются обе размерности независимо.


## Unknown quota pools

`quota_pool_id` может отсутствовать.

Quota Manager работает через `quota_attribution_group`, который может быть:

```text
confirmed
inferred
assumed_shared
unknown
```

Несколько accounts/connections одного provider не суммируются, пока независимость quota не подтверждена.

Правила guaranteed allocation:

```text
confirmed independent → разрешено
confirmed shared → одна общая квота
inferred → только с discount или opportunistic
assumed_shared → одна консервативная квота
unknown → не использовать как guaranteed capacity
```

Quota metadata из официальных открытых источников может дополнять или создавать group даже без OmniRoute `quota_pool`.


## Historical reserve and cold start

Quota Manager receives already-reserved historical forecast:

```text
historical_multiplier = 1.20
```

It must reject records where a historical source is marked as used but the reserve was not applied.

For cold-start workloads:

```text
scheduled runs come from Hermes jobs.json
usage per run comes from bootstrap profile
manual/event frequency comes from configured bootstrap rate
```

If every source is unknown, use minimum role budget with elevated safety multiplier instead of zero.
