# Модуль 09 — Role Scorer

## Цель

Оценить каждый активный бесплатный endpoint для ролей реальных агентов.

## Роли

```text
routing_fast
intake_structured
document_understanding
research_scout
constraint_optimizer
admin_finance_precision
health_reasoning
psychology_relationship
cross_domain_orchestrator
```

Подробная привязка агентов находится в `docs/architecture/03-roles-and-agents.md`.

## Eligibility filter

До scoring endpoint обязан:

- иметь разрешённый free access status;
- пройти basic probe;
- иметь достаточную usable quota;
- быть matched;
- иметь закрытый breaker;
- поддерживать required capabilities.

## Источники score

### Static

- models.dev capabilities;
- Artificial Analysis headline indices;
- OmniRoute Free Provider Rankings / Arena ELO task-fit;
- context;
- vision/tools/structured output.

### Runtime

- success rate;
- p50/p95;
- quota headroom;
- stability;
- recent failures.

### Local evals

Опциональные role-specific probe/eval scores.

## Нормализация

Каждый metric переводится в 0..1.

Latency используется относительно role SLA, а не глобально.

Quota score учитывает projected load до reset.

## Формула

```text
score =
benchmark_fit
+ capability_fit
+ health
+ latency
+ quota_headroom
+ stability
- uncertainty
```

Price не участвует: все eligible endpoint уже бесплатны в рамках доступной квоты.

## Uncertainty penalty

Штрафуется:

- low match confidence;
- provider-level telemetry вместо endpoint-level;
- мало runtime samples;
- quota rule близок к expiry;
- benchmark отсутствует.

## Сохранение

Каждая оценка immutable:

```text
role_id
endpoint_id
score_version
component_scores_json
total_score
eligibility
rejection_reasons
calculated_at
input_state_hash
```

Если `input_state_hash` не изменился, пересчёт не нужен.


## OmniRoute Arena ELO

`/api/free-provider-rankings` даёт task-fit по категориям:

```text
default
coding
review
documentation
debugging
```

Использовать как provider/model quality signal.

Ограничения:

- provider может отсутствовать, если его модели не matched с Arena;
- score относится к task category;
- это не доказательство доступности или квоты;
- Artificial Analysis и локальные evals остаются отдельными сигналами.


## Web-cookie endpoint scoring

Web-cookie endpoint проходит отдельный eligibility check.

Обязательное условие:

```text
required_role_capabilities ⊆ confirmed_endpoint_capabilities
```

Дополнительные penalties:

```text
session instability
manual/static model mapping
unknown exact model
cookie expiry risk
anti-bot/challenge risk
unknown quota
```

По умолчанию web-cookie endpoint не может стать primary и получает ограниченный maximum weight.


## Artificial Analysis scoring v1

### Разрешённые метрики

```text
intelligence_index
coding_index
agentic_index
median_output_tokens_per_second
median_end_to_end_seconds
```

### Нормализация

Все метрики переводятся в диапазон `0..1` по текущему набору сравниваемых моделей.

Для метрик, где больше лучше:

```text
normalized = clipped_minmax(value, P5, P95)
```

Для end-to-end latency:

```text
normalized_e2e = 1 - clipped_minmax(value, P5, P95)
```

### Missing values

Если отдельная метрика отсутствует:

- не подставлять 0;
- перераспределить её вес между доступными метриками;
- добавить uncertainty penalty.

Если отсутствуют все три quality index, AA quality score считается unknown.

### Базовые веса по ролям

```yaml
routing_fast:
  intelligence: 0.20
  coding: 0.00
  agentic: 0.10
  output_tps: 0.30
  end_to_end: 0.40

intake_structured:
  intelligence: 0.40
  coding: 0.05
  agentic: 0.25
  output_tps: 0.10
  end_to_end: 0.20

document_understanding:
  intelligence: 0.50
  coding: 0.00
  agentic: 0.20
  output_tps: 0.10
  end_to_end: 0.20

research_scout:
  intelligence: 0.40
  coding: 0.05
  agentic: 0.35
  output_tps: 0.10
  end_to_end: 0.10

constraint_optimizer:
  intelligence: 0.35
  coding: 0.25
  agentic: 0.30
  output_tps: 0.05
  end_to_end: 0.05

admin_finance_precision:
  intelligence: 0.50
  coding: 0.10
  agentic: 0.25
  output_tps: 0.05
  end_to_end: 0.10

health_reasoning:
  intelligence: 0.65
  coding: 0.00
  agentic: 0.20
  output_tps: 0.05
  end_to_end: 0.10

psychology_relationship:
  intelligence: 0.65
  coding: 0.00
  agentic: 0.15
  output_tps: 0.05
  end_to_end: 0.15

cross_domain_orchestrator:
  intelligence: 0.40
  coding: 0.10
  agentic: 0.40
  output_tps: 0.05
  end_to_end: 0.05
```

### Приоритет latency

```text
OmniRoute endpoint telemetry
> OmniRoute provider telemetry
> Artificial Analysis model median
```

AA latency используется как model-level baseline, а не как фактическая скорость конкретного provider endpoint.

### Итоговый AA subscore

```text
aa_score =
Σ(normalized_metric × role_weight)
- stale_penalty
- missing_data_penalty
```

AA subscore не заменяет capability eligibility, quota capacity, health, diversity и local probes.


## Context eligibility

Context используется только как hard filter.

Endpoint исключается, если:

```text
effective_context_window < role.minimum_context_window
```

или:

```text
effective_max_output_tokens < role.minimum_output_tokens
```

После прохождения minimum больший context window не добавляет отдельный score и не создаёт отдельный combo.

Если context неизвестен, endpoint исключается, кроме explicit manual override.


## Minimum quality gate

### Порядок

До расчёта weighted AA score выполняется:

```text
1. проверить capabilities;
2. проверить minimum context;
3. проверить free access;
4. проверить minimum quality gate;
5. рассчитать weighted score.
```

### Eligibility

Если у роли указан gate:

```text
model[gate.metric] >= gate.value
```

Если условие не выполнено, endpoint исключается из роли.

### Missing AA metric

Если требуемая gate-метрика отсутствует:

```text
quality_gate_status = unverifiable
```

По умолчанию endpoint исключается из этой роли.

Допускается explicit override:

```yaml
allow_unverified_quality_gate: false
```

### Индексная версия

Gate применяется только к совместимой версии Artificial Analysis index.

Если major-версия индекса изменилась:

- gate помечается `needs_recalibration`;
- новые allocation plans не применяются с непроверенным gate;
- предыдущий combo сохраняется до ручного или автоматического обновления thresholds.

### Веса после gate

Minimum gate не заменяет weighted score.

Пример:

```text
agentic_index >= 20
```

сначала отсекает слишком слабые модели, затем intelligence, agentic, coding и скорость определяют порядок оставшихся.


## Index-version binding

Каждый minimum quality gate хранит:

```text
metric
value
index_version
```

Gate действителен только для указанной версии индекса.

При обнаружении новой версии scoring engine:

- сохраняет новые metrics отдельно;
- не применяет старый raw threshold;
- ожидает завершения Index Migration.


## LLM-selected thresholds after index change

После смены index version новые raw thresholds определяются migration-agent.

Scoring engine не переносит старый threshold автоматически и не обязан сохранять тот же percentile.

Он принимает только validated migration proposal, связанный с новой index version.
