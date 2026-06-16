# Модельные роли и агенты

## routing_fast

- `00_agent_mailbox_service`
- `00_mailroom_router_agent`

## intake_structured

- `00_mail_calendar_intake_agent`
- `26_admin_initial_intake_agent`
- `27_admin_update_intake_agent`
- `24_candidate_initial_intake_agent`
- `25_candidate_update_intake_agent`
- `28_coach_therapy_session_intake_agent`

## document_understanding

- `00_document_digitizer_agent`
- `20_document_registry_agent`

## research_scout

- `01_local_setup_agent`
- `14_trip_logistics_agent`
- `16_housing_scout_agent`
- `11_eatout_delivery_scout_agent`
- `22_local_activities_agent`
- часть задач `12_personal_admin_renewal_agent`

## constraint_optimizer

- `15_flight_optimizer_agent`
- `09_meal_planning_agent`
- `10_grocery_pantry_agent`
- `19_health_training_agent`
- часть задач `14_trip_logistics_agent`

## admin_finance_precision

- `12_personal_admin_renewal_agent`
- `13_money_ops_agent`
- `20_document_registry_agent`

## health_reasoning

- `17_preventive_care_agent`
- `18_body_maintenance_agent`
- `19_health_training_agent`

## psychology_relationship

- `21_mental_health_agent`
- `06_match_analyzer`
- `23_relationship_agent`

## cross_domain_orchestrator

- `07_weekly_reset_nomad_ops_agent`


# Базовые context requirements

```yaml
routing_fast:
  minimum_context_window: 16000
  minimum_output_tokens: 1000

intake_structured:
  minimum_context_window: 32000
  minimum_output_tokens: 2000

document_understanding:
  minimum_context_window: 64000
  minimum_output_tokens: 4000

research_scout:
  minimum_context_window: 64000
  minimum_output_tokens: 4000

constraint_optimizer:
  minimum_context_window: 32000
  minimum_output_tokens: 3000

admin_finance_precision:
  minimum_context_window: 32000
  minimum_output_tokens: 3000

health_reasoning:
  minimum_context_window: 32000
  minimum_output_tokens: 3000

psychology_relationship:
  minimum_context_window: 32000
  minimum_output_tokens: 3000

cross_domain_orchestrator:
  minimum_context_window: 128000
  minimum_output_tokens: 6000
```

Это стартовые defaults. Реальные значения можно уточнить по usage history.


# Minimum quality gates

## Правило

Для роли можно задать максимум один обязательный quality gate:

```yaml
minimum_quality_gate:
  metric: intelligence_index
  value: 20
```

Разрешённые метрики:

```text
intelligence_index
coding_index
agentic_index
```

Одновременная установка нескольких minimum quality metrics запрещена.

## Стартовые значения

```yaml
routing_fast:
  minimum_quality_gate:
    metric: intelligence_index
    value: 30

intake_structured:
  minimum_quality_gate:
    metric: intelligence_index
    value: 35

document_understanding:
  minimum_quality_gate:
    metric: intelligence_index
    value: 40

research_scout:
  minimum_quality_gate:
    metric: agentic_index
    value: 45

constraint_optimizer:
  minimum_quality_gate:
    metric: intelligence_index
    value: 42

admin_finance_precision:
  minimum_quality_gate:
    metric: intelligence_index
    value: 42

health_reasoning:
  minimum_quality_gate:
    metric: intelligence_index
    value: 45

psychology_relationship:
  minimum_quality_gate:
    metric: intelligence_index
    value: 40

cross_domain_orchestrator:
  minimum_quality_gate:
    metric: agentic_index
    value: 50
```

`coding_index` пока не является minimum для существующих ролей, потому что среди них нет отдельной coding-heavy роли. Он продолжает участвовать в weighted scoring там, где полезен.

Значения являются стартовыми operational defaults и могут изменяться конфигурацией без изменения кода.


# Usage frequency and quota demand

Связь agent → role является many-to-many и содержит не только role id.

Для каждой связи хранить:

```text
calls_per_agent_run
average_input_tokens
average_output_tokens
peak_parallel_calls
```

Частота запуска хранится на уровне агента:

```text
trigger_type
cron или interval
expected_runs_per_day
p95_runs_per_day
peak_concurrency
```

Role demand рассчитывается как сумма всех использующих её агентов.

Общие роли поддерживают dependency rules:

```text
all_agent_runs → shared role
role call → shared role
```

Поэтому роль, используемая всеми агентами, получает суммарный forecast автоматически.
