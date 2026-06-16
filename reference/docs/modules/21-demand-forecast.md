
# Модуль 21 — Agent and Role Demand Forecast

## Цель

Спрогнозировать фактический расход provider quota с учётом:

```text
какие агенты используют роль
как часто запускается каждый агент
сколько раз агент вызывает роль за запуск
сколько токенов расходуется за вызов
какие общие роли вызываются всеми агентами или другими ролями
```

## Почему одного expected_requests_per_day недостаточно

Одинаковое среднее может означать разную нагрузку:

```text
7 запросов равномерно каждый день
```

и:

```text
49 запросов раз в неделю в один час
```

Для месячной квоты среднее похоже, но burst, concurrency и риск исчерпания сильно различаются.

Поэтому forecast строится по реальному горизонту до reset quota pool.

## Основные сущности

### Agent schedule profile

```text
agent_id
trigger_type
cron_expression
interval_seconds
timezone
expected_runs_per_day
p95_runs_per_day
peak_concurrency
enabled
```

Разрешённые trigger types:

```text
cron
interval
event
manual
continuous
```

Для cron и interval Orchestrator проектирует точные запуски до reset.

Для event/manual используются historical rate и conservative bootstrap estimate.

### Agent → role usage profile

```text
agent_id
role_id
calls_per_agent_run
average_input_tokens
average_output_tokens
p95_input_tokens
p95_output_tokens
peak_parallel_calls
source
confidence
```

Один агент может использовать несколько ролей.

Одна роль может использоваться многими агентами.

Все такие строки суммируются в demand одного role combo.

### Shared-role dependency

Общие служебные роли не нужно вручную дублировать для каждого агента.

Поддержать источники:

```text
all_agent_runs
agent_run
role_call
```

Поля:

```text
source_kind
source_id
target_role_id
calls_per_source_event
average_input_tokens
average_output_tokens
enabled
```

Примеры:

```yaml
# Один fetch-вызов на каждый запуск любого агента.
- source_kind: all_agent_runs
  source_id: "*"
  target_role_id: fetch
  calls_per_source_event: 1

# В среднем три fetch-вызова на один research_scout call.
- source_kind: role_call
  source_id: research_scout
  target_role_id: fetch
  calls_per_source_event: 3
```

Это примеры механизма. Реальный role id и коэффициенты задаются конфигурацией или telemetry.

## Расчёт direct demand

Для каждого агента и горизонта:

```text
projected_agent_runs =
scheduled runs before reset
или
observed event rate × horizon
```

Для каждой agent-role binding:

```text
direct_role_calls =
projected_agent_runs
× calls_per_agent_run
```

```text
direct_input_tokens =
direct_role_calls
× average_input_tokens
```

```text
direct_output_tokens =
direct_role_calls
× average_output_tokens
```

## Расчёт shared-role demand

После direct demand применяются dependencies.

Для `role_call`:

```text
target_role_calls +=
source_role_calls × calls_per_source_event
```

Для `all_agent_runs`:

```text
target_role_calls +=
sum(projected runs всех агентов)
× calls_per_source_event
```

Dependencies рассчитываются как directed acyclic graph.

Cycles запрещены:

```text
fetch → research_scout → fetch
```

Validation должна отклонить cyclic dependency graph.

## Expected и protected demand

Для allocation рассчитываются два уровня.

### Expected demand

Наиболее вероятный расход:

```text
expected calls
expected input tokens
expected output tokens
```

### Protected demand

Capacity, которую желательно зарезервировать с учётом burst:

```text
protected_calls =
max(
  p95 forecast,
  expected_calls × peak_multiplier
)
```

Аналогично для tokens.

Guaranteed quota budget строится по protected demand критичных ролей.

Opportunistic allocation может использовать expected demand.

## Quota reset horizon

Forecast строится отдельно для каждого quota pool:

```text
forecast_start = now
forecast_end = quota_pool.reset_at
```

Для rolling limits используется соответствующее rolling window.

Для monthly quota учитываются все плановые weekly/daily runs до конца месяца.

Для daily quota учитывается ближайший дневной burst.

## Telemetry learning

Приоритет источников:

```text
1. observed agent executions and role calls
2. configured schedule and calls_per_run
3. conservative bootstrap defaults
```

После достаточного количества samples Orchestrator обновляет:

```text
expected_runs
p95_runs
calls_per_run
average tokens
p95 tokens
peak concurrency
```

Рекомендуемые rolling windows:

```text
daily agents: 14–30 дней
weekly agents: 8–12 недель
monthly agents: 6–12 месяцев
event-driven: последние 30–90 дней
```

Нельзя заменять configured schedule historical average, если schedule сообщает о предстоящем известном запуске.

## New or unobserved agents

Если telemetry ещё нет:

```text
demand_source = configured
```

Если нет и конфигурации:

```text
demand_source = bootstrap
confidence = low
```

Low-confidence demand получает дополнительный safety multiplier.

## Output

Для каждой роли и quota horizon:

```text
role_id
forecast_start
forecast_end
expected_requests
protected_requests
expected_input_tokens
protected_input_tokens
expected_output_tokens
protected_output_tokens
peak_concurrency
consumer_agents
shared_dependency_breakdown
source_mix
confidence
```

## Integration with allocation

Allocator использует агрегированный role demand, а не количество агентов.

Пример:

```text
agent A → research_scout: 20 calls
agent B → research_scout: 10 calls
agent C → research_scout: 5 calls

research_scout role demand = 35 calls
```

Если каждый вызов research_scout создаёт 3 fetch calls:

```text
fetch dependency demand = 105 calls
```

Fetch получает собственный quota budget и combo capacity.

## Maintenance workloads

Отдельно учитывать:

```text
provider probes
catalog sync LLM classification
Artificial Analysis migration-agent
manual rebuilds
```

Они записываются как:

```text
consumer_type = maintenance
```

и резервируются в maintenance budget, чтобы не конкурировать скрыто с production agents.

## Acceptance criteria

1. Many agents may contribute to one role demand.
2. One agent may contribute to several roles.
3. Cron/weekly/monthly bursts are projected before quota reset.
4. Shared roles are counted through dependencies.
5. Dependency cycles are rejected.
6. Token demand is tracked separately from request demand.
7. Expected and protected demand are both available.
8. Historical telemetry overrides estimates only when sufficiently representative.
9. Maintenance usage is included.
10. Allocation cannot approve a plan that is oversubscribed after shared-role expansion.


## Hermes as demand source

Для Hermes deployments:

```text
~/.hermes/cron/jobs.json
```

даёт будущие scheduled runs, а:

```text
~/.hermes/state.db
```

даёт фактический расход по requested combo:

```text
sessions.model
sessions.input_tokens
sessions.output_tokens
sessions.api_call_count
sessions.started_at
```

Отдельный `agent_id` в session database не обязателен для quota planning, если `sessions.model` содержит имя role combo.

## Attribution limitation

Hermes показывает demand и usage combo, но не всегда показывает фактический quota pool.

Связка строится так:

```text
Hermes combo usage
→ OmniRoute selected endpoint/account when available
→ quota_attribution_group
```

Если quota attribution неизвестна:

- usage остаётся учтённым на combo/provider/endpoint level;
- endpoint не добавляет guaranteed quota capacity;
- forecast использует conservative group policy.


## Historical safety reserve

Любой forecast, основанный полностью или частично на historical usage, получает обязательный reserve:

```text
historical_reserve_multiplier = 1.20
```

Применять отдельно к:

```text
request count
input tokens
output tokens
```

Формулы:

```text
reserved_historical_requests =
historical_forecast_requests × 1.20
```

```text
reserved_historical_input_tokens =
historical_forecast_input_tokens × 1.20
```

```text
reserved_historical_output_tokens =
historical_forecast_output_tokens × 1.20
```

20% reserve применяется после нормализации historical window, но до quota allocation.

Для protected demand:

```text
protected_demand =
max(
  reserved_historical_forecast,
  historical_p95,
  exact_scheduled_forecast,
  configured_minimum
)
```

Reserve не должен применяться повторно на каждом aggregation layer. В forecast record сохраняется:

```text
base_historical_value
historical_reserve_multiplier
reserved_historical_value
```

## Cold-start procedure

Cold start означает, что для agent-role или combo ещё недостаточно representative telemetry.

### Source priority during cold start

```text
1. Exact Hermes cron/interval schedule
2. Explicit agent-role bootstrap profile
3. Role-level bootstrap profile
4. Global conservative fallback
```

### Scheduled workloads

Из `~/.hermes/cron/jobs.json` вычислить точное количество запусков до reset quota group.

Далее:

```text
cold_start_requests =
scheduled_runs
× bootstrap_calls_per_run
```

```text
cold_start_tokens =
cold_start_requests
× bootstrap_tokens_per_call
```

Bootstrap profile должен хранить:

```text
calls_per_run
input_tokens_per_call
output_tokens_per_call
peak_parallel_calls
```

### Manual and event-driven workloads

Для них расписание не даёт будущего количества запусков.

Использовать в порядке приоритета:

```text
configured bootstrap runs per day/week/month
known business cadence
global conservative fallback
```

Forecast приводится к конкретному horizon до quota reset.

### Completely unknown workload

Нулевой demand запрещён.

Если неизвестны и schedule, и configured rate:

```text
demand_source = bootstrap_unknown
confidence = very_low
```

Назначить:

```text
minimum_role_requests_per_horizon
minimum_role_input_tokens_per_horizon
minimum_role_output_tokens_per_horizon
```

и применить повышенный cold-start multiplier:

```text
cold_start_safety_multiplier = 1.50
```

Эти значения конфигурируются по роли. Они не выводятся автоматически из context window, потому что context limit не равен обычному token usage.

### Shared roles during cold start

Общие роли вроде fetch получают bootstrap demand после раскрытия dependencies:

```text
bootstrap source role calls
× calls_per_source_event
```

Если коэффициент dependency ещё неизвестен, используется configured conservative default и `confidence = low`.

## Transition from bootstrap to history

Не переключаться на historical forecast после одного-двух запусков.

Минимальные условия representative history:

```text
scheduled daily workload:
  >= 14 completed runs
  и >= 7 distinct days

scheduled weekly workload:
  >= 8 completed runs
  и >= 8 distinct scheduled periods

event/manual workload:
  >= 20 completed runs
  и >= 14 distinct days
```

Порог должен быть configurable.

### Blended transition

До достижения полной зрелости использовать blend:

```text
forecast =
bootstrap_weight × bootstrap_forecast
+
history_weight × reserved_historical_forecast
```

Где:

```text
history_weight = min(1, representative_samples / required_samples)
bootstrap_weight = 1 - history_weight
```

После достижения required samples:

```text
history_weight = 1
```

Но exact future schedule продолжает иметь приоритет по количеству запусков.

## Cold-start allocation policy

В cold start:

```text
guaranteed capacity uses protected bootstrap demand
unknown quota groups do not count as guaranteed capacity
combo remains broad enough to survive estimation error
```

Если confirmed quota недостаточно для cold-start protected demand:

```text
status = cold_start_capacity_risk
```

Orchestrator не должен молча занижать forecast.

## Acceptance criteria additions

1. Historical demand always includes exactly one 20% reserve.
2. Cold start never produces zero demand for an enabled role.
3. Hermes schedule determines run count when available.
4. Bootstrap profile supplies calls and token estimates.
5. Manual/event workloads require configured or conservative fallback rates.
6. Historical data replaces bootstrap only after representative samples.
7. Transition can be blended.
8. Exact scheduled future runs remain authoritative after transition.
