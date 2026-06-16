
# Модуль 13 — Scheduler и Jobs

## Основная модель

Orchestrator запускается один раз в сутки как batch.

Пример:

```text
15 03 * * * free-model-orchestrator daily
```

Время выбирается так, чтобы batch завершился до основной дневной нагрузки.

## Daily pipeline

```text
1. sync models.dev
2. build models.dev free_candidate_set
3. sync OmniRoute /api/free-models
4. sync OmniRoute free-provider rankings
5. validate against /api/free-tier/summary
6. build builtin no-auth provider instances and pool templates
7. discover credential provider accounts
8. merge free OAuth/API-key definitions with accounts
9. import configured web-cookie static candidates
10. build effective independent/shared quota pools
11. scan provider model catalogs
12. diff catalogs
13. research only missing/stale/ambiguous quota rules
14. classify access
15. match canonical models
16. probe new/changed endpoint
17. sync Artificial Analysis
18. read latest telemetry/usage
19. sync agent execution history
20. project scheduled agent runs until each quota reset
21. build direct agent-role demand
22. expand shared-role dependencies
23. calculate role scores
24. allocate quota pools globally
25. build large role combos
26. calculate minimal diff
27. apply
28. smoke test
29. audit
```

## Дополнительные запуски

Разрешены:

```text
manual full run
manual provider run
manual role rebuild
event-driven run после добавления provider
urgent run после явного обнаружения платного списания
```

Обычные 5-минутные и часовые cron jobs не нужны.

## Почему daily достаточно

- в каждом role combo находится много независимых моделей;
- OmniRoute обрабатывает временные ошибки;
- circuit breaker исключает неработающий endpoint во время routing;
- fallback переходит к следующей модели;
- orchestrator исправляет состав на следующем daily batch.

## Locks

```text
daily-run global lock
provider-scan lock per provider
combo-apply global lock
```

Повторный daily run не запускается, пока предыдущий не завершён.


## Artificial Analysis version-change event

После daily AA sync:

```text
if fetched_index_version != active_index_version:
    create index migration
    stop production threshold recalculation
    keep current combos active
```

Index migration запускается как отдельный event-driven workflow и не блокирует остальные daily sync steps, кроме применения новых AA-based scoring plans.


## LLM migration task

Index migration выполняется отдельной maintenance-задачей.

Она динамически выбирает healthiest available endpoint модели с максимальным новым `intelligence_index`.

Задача не входит в обычные role combo и получает отдельный maintenance quota reservation.


## Demand forecast refresh

Demand forecast пересчитывается:

```text
в daily batch
после изменения agent schedule
после изменения agent-role binding
после изменения shared-role dependency
после существенного usage drift
```

Перестройка combo нужна только если новый forecast меняет quota feasibility или allocation weights.


## Optional smart review step

After building and validating changed combo:

```text
if smart review trigger matched:
  call reviewer once
  validate each add/remove/move diff
  apply accepted diffs to copy
  full validate
```

Reviewer failure or absence of valid diffs does not block the deterministic combo.


## Daily Hermes inventory

Run full Hermes inventory every day using `HERMES_INVENTORY_CRON`.

The inventory refreshes:

```text
roles
profiles per role
routines per role
schedules
calls_per_run
expected frequency
```

An unknown role triggers an immediate full inventory outside the normal schedule.

If consumers or frequency changed:

```text
refresh Inspector forecast
→ recalculate protected demand
→ run normal allocation
```

The scheduler never calls `/api/combos/test`.
