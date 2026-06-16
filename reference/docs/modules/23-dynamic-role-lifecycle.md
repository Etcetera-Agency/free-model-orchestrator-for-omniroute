
# Модуль 23 — Hermes Role Inventory and Lifecycle

## Цель

Поддерживать актуальный реестр:

```text
role
→ какие Hermes agent profiles её используют
→ какие routines её используют
→ как часто они запускаются
→ сколько role calls делает один запуск
→ текущий forecast
```

Orchestrator не пытается выводить роли из runtime history как основной механизм.

## Daily inventory

Полная инвентаризация Hermes выполняется ежедневно:

```text
load all agent profiles
load all routines
load enabled cron jobs
extract role references
extract schedules and expected frequency
extract calls_per_run
update role consumer registry
```

Default schedule:

```yaml
hermes_inventory:
  schedule: "0 4 * * *"
  timezone: "Europe/Bucharest"
```

Кроме ежедневного запуска поддерживается manual trigger.

## Immediate inventory on unknown role

Если в Hermes usage, cron, config event или OmniRoute request замечено имя роли, которого нет в registry:

```text
unknown role detected
→ immediately run full Hermes inventory
→ locate every profile and routine using that role
→ calculate their frequency
→ update registry
→ Inspector creates initial forecast
→ continue normal allocation
```

Не выполнять частичный поиск только по одному найденному агенту: при новой роли всегда делается полная инвентаризация Hermes.

## Role registry

Для каждой роли хранить:

```text
role name
status
first_seen_at
last_inventory_at
profiles using role
routines using role
schedule per consumer
expected runs per quota window
calls_per_run
estimated input tokens per call
estimated output tokens per call
peak concurrency
forecast source
forecast confidence
current forecast
```

Пример:

```yaml
role: research_scout
profiles:
  - profile: 14_trip_logistics_agent
    calls_per_run: 2
    trigger: manual
    expected_runs_per_week: 3

routines:
  - routine: daily_trip_monitor
    schedule: "0 9 * * *"
    calls_per_run: 1
```

## Inventory diff

После каждой ежедневной инвентаризации сравнивать новый inventory с предыдущим:

```text
new role
removed role
new consumer
removed consumer
schedule changed
calls_per_run changed
profile changed
routine changed
```

Если изменился состав потребителей или частота роли:

```text
mark forecast stale
→ run Inspector forecast refresh
→ apply 20% historical/bootstrap reserve
→ run normal quota allocation
→ rebuild combo only if resulting allocation materially changed
```

## Inspector forecast

Inspector получает:

```text
role name
all profiles using role
all routines using role
descriptions
schedules
manual/event expected frequency
calls_per_run
known token estimates
shared role dependencies
```

Inspector возвращает базовый forecast:

```json
{
  "role": "legal_research",
  "expected_runs_per_window": 8,
  "expected_calls_per_window": 12,
  "average_input_tokens": 12000,
  "average_output_tokens": 2500,
  "peak_concurrency": 1,
  "confidence": "low",
  "assumptions": []
}
```

Inspector выполняется через тот же `Instructor`-runtime, что и остальные
structured-LLM шаги (OpenAI SDK → OmniRoute → модель → Instructor → валидируемый
Pydantic forecast). Это один из Instructor-сайтов проекта наряду с quota-research,
smart-combo-reviewer и migration-agent.

Inspector не выбирает модели и не изменяет quota attribution.

## Forecast lifecycle

Для новой или существенно изменённой роли:

```text
Inspector bootstrap forecast
→ protected demand
→ normal allocation
```

После накопления representative history:

```text
bootstrap
→ blended bootstrap/history
→ historical forecast + 20% reserve
```

Ежедневная инвентаризация обновляет структуру потребления даже после перехода на historical forecast. Точное новое расписание имеет приоритет над старой историей.

## Removed role

Если после ежедневной полной инвентаризации роль не используется ни одним profile и ни одной routine:

```text
status = inactive
missing_since = now
keep current combo during grace period
```

Если роль снова появляется:

```text
status = active
clear missing_since
refresh consumers and forecast
```

Удаление combo разрешено только после grace period и отсутствия недавнего runtime usage.

## Hermes inventory adapters

Orchestrator поддерживает один из режимов:

```text
filesystem
command
http
```

### Filesystem

Читает Hermes files напрямую из `HERMES_HOME`.

### Command

Запускает локальную команду из `HERMES_INVENTORY_COMMAND`, которая возвращает normalized JSON inventory.

### HTTP

Запрашивает `HERMES_INVENTORY_URL` с optional bearer token.

Все adapter modes должны приводить данные к одной внутренней схеме.

## Environment configuration

Пути, URL и секреты задаются через environment variables.

Не хранить ключи в YAML или database snapshots.

Обязательные параметры зависят от выбранного adapter mode.

## Local dry-run

После forecast и allocation выполняется локальная проверка итогового combo без upstream model calls.

`POST /api/combos/test` автоматически не используется.

## Acceptance criteria

1. Full Hermes inventory runs daily.
2. Unknown role triggers immediate full inventory.
3. Registry stores profiles, routines and their frequency per role.
4. Consumer/schedule changes refresh the role forecast.
5. Inspector creates the initial forecast for a new role.
6. Runtime history does not replace structural inventory.
7. Removed role becomes inactive before retirement.
8. Paths, URLs and tokens are supplied through environment variables.
9. Missing required environment variables fail startup with a clear error.
10. Secrets are never sent to Inspector.
