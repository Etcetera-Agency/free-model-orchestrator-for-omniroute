# Free Model Orchestrator — ТЗ v3.19

Версия: **3.19**

## Назначение

Отдельный сервис, который поддерживает в OmniRoute актуальный набор моделей, доступных без денежных списаний:

- модели с нулевой ценой;
- модели с обычной платной ценой, но доступные через конкретный provider/account внутри подтверждённой бесплатной квоты;
- временные promo/free-tier модели, пока лимит действует.

Сервис не заменяет runtime-routing OmniRoute. Он формирует и обновляет role-combo, а OmniRoute выполняет запросы, fallback и retries.

Hermes/OpenClaw не участвует в работе сервиса.

## Главный инвариант

```text
Ни один probe или production request не должен выйти за пределы подтверждённой бесплатной ёмкости.
```

Если бесплатный доступ нельзя подтвердить или безопасно ограничить, endpoint не используется.

## Поток данных

Основной процесс выполняется **один раз в сутки**.

```text
models.dev
  ├─ cost = 0
  └─ "free" в названии/ID
        ↓
Начальный список бесплатных кандидатов
        ↓
Сопоставление с моделями всех OmniRoute providers
        ↓
Проверка provider-specific free quota
        ↓
Безопасный probe новых/изменившихся endpoint
        ↓
Artificial Analysis + capabilities + latency
        ↓
Role scoring
        ↓
Большие combo по каждой роли
        ↓
Минимальный diff → OmniRoute
```

OmniRoute самостоятельно обрабатывает runtime fallback, временные ошибки и circuit breaker. Поэтому orchestrator не должен постоянно пересобирать combo в течение дня.

## Состав архива

- `docs/architecture/` — общий поток, состояния и интерфейсы.
- `docs/modules/` — подробное ТЗ каждого модуля.
- `db/schema.sql` — рекомендуемая схема PostgreSQL.
- `config/config.example.yaml` — пример конфигурации.
- `schemas/` — контракты структурированных данных.
- `tests/test-plan.md` — тесты и acceptance criteria.
- `legacy/spec-v2.4.md` — предыдущая сводная версия.

## Порядок реализации

1. Ежедневная загрузка models.dev и выделение бесплатных кандидатов.
2. Сопоставление кандидатов с моделями всех OmniRoute providers.
3. Quota Research для provider-specific free quota.
4. Access Classifier и безопасный probe новых/изменившихся endpoint.
5. Artificial Analysis, capabilities и сохранённая telemetry.
6. Role Scorer.
7. Формирование больших combo по ролям.
8. Применение минимального diff, audit и rollback.


## Artificial Analysis scoring v1

Для базового сравнения моделей используются только:

```text
intelligence_index
coding_index
agentic_index
median_output_tokens_per_second
median_end_to_end_seconds
```

Остальные поля Artificial Analysis сохраняются только в raw snapshot и не участвуют в scoring v1.


## Context-window eligibility

Для каждого endpoint рассчитываются:

```text
effective_context_window
effective_max_output_tokens
```

У каждой роли есть только один параметр:

```text
minimum_context_window
```

Endpoint либо проходит minimum роли и может участвовать в единственном role combo, либо исключается.


## Minimum quality gate per role

Роль может иметь не более одного обязательного порога Artificial Analysis:

```yaml
minimum_quality_gate:
  metric: intelligence_index | coding_index | agentic_index
  value: number
```

Порог используется как hard filter. Веса Artificial Analysis применяются только для сортировки моделей, уже прошедших gate.


## Artificial Analysis index migration

При изменении major/minor версии Artificial Analysis index запускается отдельная migration procedure.

До её завершения:

- старые thresholds не применяются к новой версии индекса;
- новые allocation plans не активируются;
- текущие role combo продолжают работать;
- система готовит новые thresholds и отчёт для validation.


## LLM-driven index migration

При изменении Artificial Analysis index решение о новых role thresholds готовит отдельный migration-agent.

Для него выбирается доступная модель с максимальным значением нового `intelligence_index`.

Детерминированный код:

- собирает old/new distributions;
- передаёт migration-agent данные по ролям и capacity;
- валидирует его structured proposal;
- выполняет dry-run;
- применяет только безопасный результат.


## Migration-agent runtime

Для migration-agent используется `Instructor` поверх OpenAI-compatible API OmniRoute.

Отдельный agent framework не используется.

```text
OpenAI SDK
→ OmniRoute
→ selected migration model
→ Instructor
→ Pydantic MigrationProposal
→ deterministic validator
```

Instructor отвечает только за structured output, Pydantic validation и автоматические repair retries.


## Demand-aware quota allocation

Quota allocation учитывает не только роль, но и её реальных потребителей:

```text
agent schedule
× expected agent runs
× role calls per agent run
× tokens per role call
+ shared-role fan-out
```

Несколько агентов могут использовать один role combo. Их нагрузка суммируется.

Общие служебные роли, например fetch, могут рассчитываться как зависимость от всех agent runs или от вызовов других ролей.


## Quota attribution with incomplete pool knowledge

Фактический расход роли определяется по combo и endpoint usage, но `quota_pool` не всегда известен напрямую.

Каждый endpoint/account получает quota attribution status:

```text
confirmed
inferred
assumed_shared
unknown
```

Несколько аккаунтов считаются независимой capacity только при `confirmed`. В остальных случаях Orchestrator не суммирует их квоты автоматически.


## Historical reserve and cold start

Forecast, рассчитанный по историческим данным, всегда умножается на:

```text
1.20
```

На старте без истории Orchestrator использует:

```text
Hermes schedule
× bootstrap calls per run
× bootstrap tokens per call
```

Для manual/event-driven workload применяется настроенный bootstrap rate. Если он отсутствует, используется минимальный role bootstrap budget с низкой confidence и повышенным safety reserve.


## Smart combo review

Перед применением новых combo Orchestrator может выполнить один advisory review через наиболее сильную доступную модель.

Reviewer видит готовые ordered priority combo и может предложить только:

```text
add endpoint
remove endpoint
move endpoint
```

Веса, weighted routing и изменение routing strategy не используются.


## Dynamic role lifecycle

Hermes roles are not assumed to be static.

The orchestrator continuously reconciles the desired Hermes role set with managed OmniRoute combos:

```text
discover desired roles
→ create missing managed roles
→ update active roles
→ mark missing roles as retiring
→ delete only after grace period and zero observed use
```

A role is never deleted immediately after disappearing from one scan.


## Daily Hermes inventory

Orchestrator stores the current role registry together with every profile/routine that uses each role and its frequency.

A full Hermes inventory runs daily. An unknown role triggers the same full inventory immediately.

Connection paths and URLs are configured in `.env`; see `.env.example`.
