# Changelog

## 3.19

- Добавлен optional smart review уже собранных role combo.
- Reviewer запускается одним structured LLM call через Instructor.
- Reviewer может предложить только add/remove/move endpoint.
- Все role combo используют ordered `priority` routing.
- Endpoint weights и стратегия `weighted` исключены.
- Reviewer не может менять quota, quality gates, capabilities, demand или provider metadata.
- Каждый diff валидируется детерминированным кодом; невалидные операции игнорируются отдельно.

## 3.16

- Добавлен обязательный 20% reserve поверх historical demand forecast.
- Historical requests и tokens умножаются на 1.20 до allocation.
- Добавлена cold-start процедура для deployment без usage history.
- Scheduled jobs используют точный Hermes schedule и bootstrap usage profile.
- Manual/event-driven workloads используют configured bootstrap rate.
- При отсутствии любой оценки роль получает minimum bootstrap budget, а не нулевой demand.
- Переход от bootstrap к historical forecast выполняется постепенно после достаточного количества samples.

## 3.15

- Demand forecasting привязан к combo usage из Hermes `state.db`.
- Provider quota attribution больше не требует всегда известного `quota_pool`.
- Добавлены quota attribution statuses: confirmed, inferred, assumed_shared, unknown.
- Поддержаны quota сведения из OmniRoute и открытых источников.
- Несколько аккаунтов одного provider не считаются независимыми автоматически.
- Unknown/inferred pools используются консервативно и не увеличивают guaranteed capacity.
- Добавлено сопоставление requested combo → actual endpoint/account → quota attribution group.

## 3.14

- Добавлен demand forecasting на связке agent → role.
- Учитываются cadence, cron/interval/event triggers, calls per run, tokens per call и burst concurrency.
- Нагрузка нескольких агентов на один role combo суммируется.
- Добавлены shared-role dependencies для общих ролей вроде fetch.
- Demand рассчитывается до фактического reset каждого quota pool, а не только как среднее за день.
- Historical telemetry постепенно заменяет bootstrap estimates.
- Global allocation теперь использует expected и protected demand.
- Исправлены ранее согласованные realistic quality gates.

## 3.13

- Зафиксирован Instructor как runtime для migration-agent.
- Отдельный agent framework исключён.
- Migration-agent реализуется как один structured LLM call через OmniRoute.
- Pydantic schema определяет MigrationProposal.
- Instructor выполняет JSON parsing, validation и repair retries.
- Operational validation и rollout остаются в собственном детерминированном коде.

## 3.12

- Artificial Analysis index migration упрощена до LLM-driven procedure.
- Migration-agent использует доступную модель с максимальным новым intelligence index.
- LLM самостоятельно анализирует смену шкалы и предлагает thresholds по ролям.
- Percentile mapping остаётся входным сигналом, а не обязательным алгоритмом решения.
- Детерминированный код выполняет schema validation, capacity checks, dry-run и rollout.
- При недоступности migration model production thresholds и combo не меняются.

## 3.11

- Добавлена отдельная процедура миграции Artificial Analysis index.
- Смена версии индекса больше не пересчитывает thresholds молча.
- Старые thresholds замораживаются и привязываются к прежней index version.
- Для новой версии строятся распределения, percentiles и suggested thresholds.
- Новые thresholds проходят validation на combo size, quality и quota capacity.
- Rollout выполняется только после approval.
- При ошибке сохраняются прежние combo и thresholds.

## 3.10

- Добавлен один optional minimum quality gate на роль.
- Gate может использовать только одну из метрик: intelligence, coding или agentic.
- Одновременные три минимальных порога запрещены.
- Gate применяется до weighted scoring как hard filter.
- Weighted AA score остаётся механизмом ранжирования прошедших моделей.
- Добавлены стартовые quality gates для ролей.

## 3.9

- Context policy упрощена до одного параметра `minimum_context_window` на роль.
- Удалены preferred context, context buckets и similarity ratio.
- Удалены medium/large/xlarge sub-combo.
- Для каждой роли снова создаётся один combo.
- Endpoint допускается, если его effective context не меньше minimum роли.
- `effective_max_output_tokens` сохраняется как отдельное hard requirement.

## 3.8

- Добавлен context-window-aware allocation.
- Context window определяется на уровне provider endpoint, а не только canonical model.
- Добавлены `effective_context_window` и `effective_max_output_tokens`.
- Модели группируются в похожие context buckets.
- Запрещён unsafe fallback с длинного контекста на существенно меньший.
- Добавлены role-specific minimum context requirements.
- Размер контекста включён в eligibility, scoring и allocation.

## 3.7

- Зафиксирован минимальный набор Artificial Analysis для scoring v1.
- Используются только intelligence, coding, agentic, output TPS и end-to-end latency.
- Остальные AA-поля исключены из scoring v1.
- Добавлена нормализация пяти метрик в диапазон 0..1.
- End-to-end latency инвертируется: меньше — лучше.
- Реальная OmniRoute endpoint telemetry имеет приоритет над AA median latency.
- Добавлены базовые веса по ролям.

## 3.6

- Web-cookie providers снова разрешены в role combo.
- Они остаются вне automatic model discovery и daily model refresh.
- Добавлена capability-gated схема допуска web-cookie endpoint.
- Web-cookie endpoint разрешён только для ролей без обязательного tool calling, structured output, vision и других API-specific capabilities.
- Их модели задаются статически/manual и проходят отдельный basic text probe.

## 3.5

- Web-cookie providers исключены из автоматического model discovery.
- Их модели не обновляются из provider registry и не попадают в role combo автоматически.
- Web-cookie integrations остаются manual/static и вне daily batch.
- Удалены web-cookie providers из free registry merge, scoring, probe и allocation.

## 3.4

- Добавлен Free Provider Registry Sync.
- Добавлены OmniRoute API `/api/free-models`, `/api/free-provider-rankings`, `/api/free-tier/summary`.
- No-auth providers больше не обнаруживаются через `/api/providers`.
- `poolKey` OmniRoute используется как основной сигнал общей квоты моделей.
- Добавлены free provider classes: noauth, oauth, apikey, web-cookie/provider-specific.
- Добавлены `freeType`, documented budgets, recurring/one-time/discontinued статусы и ToS verdict.
- No-auth quota scope разделён на IP, installation, device/session и global public pool.
- Добавлен OmniRoute Arena ELO как дополнительный quality signal.

## 3.3

- Добавлен отдельный Account Discovery модуль.
- Количество provider connections больше не считается автоматически количеством независимых квот.
- Добавлено сопоставление connections с quota pools.
- Добавлены no-auth virtual accounts.
- Capacity рассчитывается только по независимым quota pools.
- Добавлены API-вызовы `/api/providers` и `/api/rate-limits` в account discovery flow.

## 3.2

- Allocation переведён с независимого построения combo на глобальное распределение всех ролей.
- Добавлены role quota budgets и reserved capacity по quota pool.
- Один endpoint может присутствовать в нескольких combo, но его вес ограничивается общей ёмкостью quota pool.
- Добавлены правила против конкуренции ролей за одну и ту же бесплатную квоту.
- Размер combo теперь является верхней целью, а не обязательным числом моделей.

## 3.1

- Основной процесс переведён на один ежедневный batch.
- models.dev стал первым источником кандидатов: `cost = 0` и `free` в названии/ID.
- Убраны обязательные 5-минутные циклы health и quota.
- Runtime-ошибки и временные отказы оставлены OmniRoute fallback/circuit breaker.
- Combo для каждой роли должны содержать много независимых моделей.
- Внеплановый запуск остаётся ручным или event-driven.

## 3.0

- ТЗ разбито на отдельные исполнимые модули.
- Для каждого модуля описаны входы, внешние вызовы, сравнения, запись в БД, состояния и ошибки.
- Добавлены точные OmniRoute API, подтверждённые текущей официальной документацией.
- Добавлены provider adapter contracts.
- Подробно описан internet quota research.
- Добавлены SQL schema, JSON schemas, scheduler, state machines и test plan.
- Предыдущая версия сохранена отдельно.

## 2.4

- Добавлен высокоуровневый quota research.
