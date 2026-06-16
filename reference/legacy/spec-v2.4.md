# ТЗ v2: Free Model Orchestrator для OmniRoute

Версия: 2.4


## 1. Цель

Создать отдельный сервис/скрипт `free-model-orchestrator`, основная задача которого — автоматически поддерживать актуальный набор **бесплатных моделей** у всех провайдеров, зарегистрированных в OmniRoute.

Сервис должен:

- регулярно опрашивать каждый подключённый OmniRoute provider;
- находить новые бесплатные модели, которые появились у провайдера;
- обнаруживать модели, которые перестали быть бесплатными, исчезли или перестали работать;
- учитывать, что каталоги бесплатных моделей у Kilo и других провайдеров меняются без предупреждения;
- автоматически проверять доступность новых моделей реальным тестовым запросом;
- измерять фактическую latency и error rate;
- получать metadata из models.dev;
- получать независимые scores из Artificial Analysis;
- сопоставлять одинаковые модели между разными провайдерами;
- распределять бесплатные модели по модельным ролям агентов;
- учитывать квоты, rate limits и общие quota pools;
- не вешать все роли на одного провайдера или один общий quota pool;
- автоматически обновлять role-combo в OmniRoute;
- хранить историю изменений и поддерживать rollback.

Модели с оплатой за фактическое использование вне бесплатного лимита не должны использоваться. При этом модель с обычной платной ценой может входить в scope, если конкретный provider/account предоставляет для неё подтверждённую бесплатную квоту и сервис умеет контролировать её остаток.

Hermes/OpenClaw не участвует в работе сервиса и может ничего о нём не знать.

---

## 2. Общая архитектура

```text
OmniRoute providers ─────┐
(Kilo, AGY, etc.)        │
                        ├──> Free Model Orchestrator ───> OmniRoute role-combo
models.dev ──────────────┤              │
Artificial Analysis ────┘              └──> PostgreSQL
```

Компоненты:

1. `provider-scanner` — опрос всех зарегистрированных OmniRoute providers.
2. `free-model-detector` — определение бесплатных моделей и изменений их статуса.
3. `probe-runner` — реальные тестовые запросы к новым и подозрительным endpoint.
4. `quota-research` — поиск и верификация бесплатных квот в интернете.
11. `telemetry-sync` — health, errors, latency и usage.
6. `quota-manager` — расчёт доступной бесплатной ёмкости.
7. `model-matcher` — сопоставление моделей между источниками.
8. `role-scorer` — оценка бесплатных моделей для ролей.
9. `allocator` — распределение ролей по провайдерам и quota pools.
10. `config-applier` — обновление role-combo в OmniRoute.
11. `audit-log` — история изменений и rollback.

---

## 2.1. Основной сценарий

```text
1. Получить из OmniRoute список всех зарегистрированных providers.
2. Для каждого provider получить текущий список моделей.
3. Для каждого provider обновить quota evidence через API и интернет-поиск.
4. Определить модели с нулевой ценой или доступом внутри подтверждённой free quota.
5. Сравнить результат с предыдущим snapshot.
5. Найти:
   - новые бесплатные модели;
   - исчезнувшие модели;
   - модели, которые стали платными;
   - модели с изменившимся ID;
   - модели, которые формально есть, но фактически не отвечают.
6. Выполнить probe новых и изменившихся endpoint.
7. Обновить health, latency, quota и benchmark metadata.
8. Пересчитать пригодность моделей для ролей.
9. Пересобрать role-combo с учётом diversity и quota pools.
10. Применить минимальный diff через OmniRoute API.
```

Основным источником фактической доступности является сам provider через OmniRoute, а не models.dev или Artificial Analysis.

## 3. Источники данных

### 3.1 OmniRoute и зарегистрированные providers

OmniRoute является главным реестром провайдеров, которые нужно сканировать.

Получать через API:

- список всех зарегистрированных providers;
- provider type и account/credential;
- список моделей каждого provider;
- цену input/output, если provider её отдаёт;
- provider-specific признаки `free`, `trial`, `promo`, `free-tier`;
- текущие `combo`;
- health провайдеров и моделей;
- circuit breaker / lockout;
- ошибки по endpoint;
- latency `p50`, `p95`, `p99`;
- количество запросов;
- расход токенов;
- rate limits;
- остаток квоты;
- время сброса квоты;
- concurrency limits.

Сканирование выполняется для всех providers без ручного списка. Новый provider, зарегистрированный в OmniRoute, должен автоматически попасть в следующий scan.

Особенно важно поддержать провайдеры с динамическим каталогом бесплатных моделей, например Kilo, где набор доступных моделей может регулярно меняться.

Если OmniRoute не отдаёт каталог конкретного provider, предусмотреть provider adapter, который получает каталог через нативный API провайдера.

Если OmniRoute не отдаёт точную квоту, использовать локальную конфигурацию и расчёт usage.

### 3.2 models.dev

Использовать для:

- обнаружения новых моделей;
- canonical model name;
- developer/model family;
- context window;
- modalities;
- vision;
- tool calling;
- structured output;
- reasoning;
- pricing;
- даты появления;
- статуса модели.

Источник не считается доказательством того, что модель реально доступна через подключённый OmniRoute provider.

### 3.3 Artificial Analysis

Использовать для независимой оценки качества:

- Intelligence Index;
- coding score;
- agentic score;
- scientific reasoning score;
- multilingual score;
- output speed;
- TTFT;
- price;
- available benchmark metadata.

Обновлять не чаще одного раза в сутки.

---

## 3.3. Quota Research: поиск бесплатных квот в интернете

Не все провайдеры отдают бесплатные лимиты через API. Для таких случаев сервис должен иметь отдельный интернет-поиск по каждому зарегистрированному provider.

Источники по приоритету:

1. официальная API-документация;
2. официальный pricing/free-tier page;
3. официальный dashboard/help center;
4. официальный changelog или release notes;
5. официальный GitHub repository;
6. сообщения команды провайдера в официальных community-каналах;
7. сторонние источники — только как неподтверждённая подсказка.

Для каждого provider искать:

```text
free models
free tier
free quota
daily limit
monthly limit
rate limit
requests per day
tokens per day
reset time
trial quota
promo quota
fair use
```

Поиск должен учитывать provider aliases и конкретные способы авторизации:

```text
Kilo
Kilo Code
OpenCode Free
MiMoCode Free
Antigravity
AGY
```

Результат сохраняется как структурированная запись:

```json
{
  "provider": "kilo",
  "account_type": "free",
  "model_pattern": "*",
  "quota_type": "requests_per_day",
  "quota_limit": 100,
  "reset_policy": "calendar_day",
  "hard_stop_confirmed": true,
  "source_url": "...",
  "source_type": "official_docs",
  "source_published_at": null,
  "checked_at": "...",
  "confidence": 0.95,
  "evidence": "..."
}
```

LLM используется для извлечения структуры из страниц, но не считается источником. Каждое утверждение должно иметь URL и короткий evidence fragment.

Если найдено несколько противоречащих значений:

1. предпочесть более новый официальный источник;
2. учитывать дату публикации и дату проверки;
3. пометить quota state как `conflicting`;
4. не использовать endpoint автоматически до разрешения конфликта.

Если точный лимит не найден:

```text
quota_status = undocumented
```

Такой endpoint можно использовать только если provider гарантирует hard stop без платного списания. Иначе он исключается.

### Периодичность quota research

- при добавлении нового provider — сразу;
- при появлении новой модели — сразу;
- для активных providers — раз в сутки;
- для undocumented/conflicting — каждые 6 часов;
- после HTTP 402/429 или неожиданного quota error — внепланово;
- полная перепроверка всех источников — раз в неделю.

### Кэш и актуальность

Для quota evidence хранить:

```text
source_url
source_hash
source_type
published_at
first_seen_at
last_checked_at
last_changed_at
confidence
raw_excerpt
parsed_rule_json
```

Если страница изменилась, правило квоты должно пройти повторный parsing и validation до применения.

## 3.4. Жёсткий инвариант Free-only

Решение принимается на уровне конкретного `provider endpoint + account`, а не по глобальной цене canonical model.

Разрешены:

```text
модель с нулевой ценой
модель внутри подтверждённой free quota
модель внутри подтверждённого promotional/free-tier лимита
```

Запрещены:

```text
запрос после исчерпания бесплатной квоты
endpoint без возможности надёжно определить остаток free quota
автоматическое списание денег
платный fallback
```

Если бесплатная квота исчерпана, endpoint немедленно исключается из routing до следующего reset. Если бесплатных endpoint для роли нет, роль получает статус `degraded` или `unavailable`.

## 3.5. Определение бесплатной модели

Endpoint считается бесплатным только на уровне конкретного provider/account.

Одна и та же canonical model может быть:

```text
бесплатной у Kilo
бесплатной по quota у AGY
платной у OpenRouter
недоступной у другого provider
```

Статусы доступности endpoint:

```text
free_unlimited
free_quota_available
free_quota_exhausted
free_promotional_available
free_promotional_expired
paid_only_excluded
unknown_excluded
unavailable
```

Приоритет определения:

1. Явная бесплатная квота provider/account с известным остатком и reset.
2. Явный provider flag `free`.
3. Цена input/output равна нулю.
4. Provider-specific бесплатный каталог.
5. Локальная конфигурация лимита.
6. Реальный probe только при гарантии отсутствия списания.
7. `unknown_excluded`, если определить безопасно невозможно.

В production-combo включать только `free_unlimited`, `free_quota_available` и `free_promotional_available`.

Pricing metadata используется только для подтверждения бесплатности или исключения endpoint, а не для выбора среди платных вариантов.

Хранить:

```text
access_status
list_input_price
list_output_price
currency
free_quota_type
free_quota_limit
free_quota_used
free_quota_remaining
free_quota_reset_at
free_quota_source
can_hard_stop_at_zero
access_checked_at
```

Если бесплатная квота закончилась или исчезла:

1. немедленно убрать endpoint из всех combo;
2. пометить его как `free_quota_exhausted`, `free_promotional_expired` или `paid_only_excluded`;
3. не выполнять дополнительные запросы до подтверждённого reset;
4. записать изменение в audit log;
5. подобрать другой endpoint с доступной бесплатной ёмкостью;
6. вернуть endpoint после reset только после обновления quota state и безопасного probe.

## 4. Основные сущности

### 4.1 Canonical Model

Логическая модель независимо от провайдера.

Примеры:

```text
claude-sonnet-4.6
gemini-2.5-pro
qwen3-coder
```

### 4.2 Provider Endpoint

Конкретный путь к модели:

```text
antigravity/claude-sonnet-4.6
agy/claude-sonnet-4.6
openrouter/qwen3-coder
```

### 4.3 Account

Конкретная авторизация или API key.

### 4.4 Quota Pool

Группа endpoint/account, использующих общую квоту.

Пример:

```yaml
providers:
  antigravity:
    provider_group: google
    quota_pool: google_account_1

  agy:
    provider_group: google
    quota_pool: google_account_1
```

### 4.5 Provider Group

Группа общего инфраструктурного риска:

```text
google
anthropic
openrouter
github
nvidia
aws
```

Разные названия провайдеров могут входить в одну группу.

---

## 5. Модельные роли

### 5.1 `routing_fast`

Агенты:

- `00_agent_mailbox_service`
- `00_mailroom_router_agent`

Требования:

- минимальная latency;
- низкая стоимость;
- стабильный structured output;
- хорошая классификация;
- tool calling при необходимости.

### 5.2 `intake_structured`

Агенты:

- `00_mail_calendar_intake_agent`
- `26_admin_initial_intake_agent`
- `27_admin_update_intake_agent`
- `24_candidate_initial_intake_agent`
- `25_candidate_update_intake_agent`
- `28_coach_therapy_session_intake_agent`

Требования:

- точное извлечение фактов;
- отсутствие выдуманных данных;
- корректное обновление существующих записей;
- строгий JSON/schema adherence;
- хороший multilingual.

### 5.3 `document_understanding`

Агенты:

- `00_document_digitizer_agent`
- `20_document_registry_agent`

Требования:

- vision;
- OCR/document understanding;
- длинный контекст;
- извлечение структурированных полей;
- работа с таблицами и плохими сканами.

### 5.4 `research_scout`

Агенты:

- `01_local_setup_agent`
- `14_trip_logistics_agent`
- `16_housing_scout_agent`
- `11_eatout_delivery_scout_agent`
- `22_local_activities_agent`
- частично `12_personal_admin_renewal_agent`

Требования:

- web/tool calling;
- мультиязычность;
- длинный контекст;
- сравнение вариантов;
- работа с актуальными ценами, условиями и расписаниями.

### 5.5 `constraint_optimizer`

Агенты:

- `15_flight_optimizer_agent`
- `09_meal_planning_agent`
- `10_grocery_pantry_agent`
- `19_health_training_agent`
- частично `14_trip_logistics_agent`

Требования:

- reasoning;
- работа с ограничениями;
- даты и расчёты;
- structured output;
- устойчивость к изменению входных данных.

### 5.6 `admin_finance_precision`

Агенты:

- `12_personal_admin_renewal_agent`
- `13_money_ops_agent`
- `20_document_registry_agent`

Требования:

- высокая точность;
- расчёты;
- сроки;
- structured output;
- низкий hallucination rate;
- возможность независимой проверки второй моделью.

### 5.7 `health_reasoning`

Агенты:

- `17_preventive_care_agent`
- `18_body_maintenance_agent`
- `19_health_training_agent`

Требования:

- сильный reasoning;
- длинный персональный контекст;
- осторожность;
- risk triage;
- высокая надёжность.

### 5.8 `psychology_relationship`

Агенты:

- `21_mental_health_agent`
- `06_match_analyzer`
- `23_relationship_agent`

Требования:

- long-context reasoning;
- хороший язык;
- мультиязычность;
- анализ диалогов;
- эмпатичность;
- корректная работа с персональным контекстом.

### 5.9 `cross_domain_orchestrator`

Агент:

- `07_weekly_reset_nomad_ops_agent`

Требования:

- очень длинный контекст;
- planning;
- приоритизация;
- объединение результатов других агентов;
- structured output;
- высокая надёжность.

---

## 6. Привязка агентов к ролям

```yaml
00_agent_mailbox_service:
  roles: [routing_fast]

00_mailroom_router_agent:
  roles: [routing_fast]

00_mail_calendar_intake_agent:
  roles: [intake_structured]

00_document_digitizer_agent:
  roles: [document_understanding]

01_local_setup_agent:
  roles: [research_scout]

14_trip_logistics_agent:
  roles: [research_scout, constraint_optimizer]

15_flight_optimizer_agent:
  roles: [constraint_optimizer]

16_housing_scout_agent:
  roles: [research_scout]

09_meal_planning_agent:
  roles: [constraint_optimizer]

10_grocery_pantry_agent:
  roles: [constraint_optimizer]

11_eatout_delivery_scout_agent:
  roles: [research_scout]

12_personal_admin_renewal_agent:
  roles: [admin_finance_precision, research_scout]

13_money_ops_agent:
  roles: [admin_finance_precision]

20_document_registry_agent:
  roles: [document_understanding, admin_finance_precision]

26_admin_initial_intake_agent:
  roles: [intake_structured]

27_admin_update_intake_agent:
  roles: [intake_structured]

17_preventive_care_agent:
  roles: [health_reasoning]

18_body_maintenance_agent:
  roles: [health_reasoning]

19_health_training_agent:
  roles: [constraint_optimizer, health_reasoning]

21_mental_health_agent:
  roles: [psychology_relationship]

28_coach_therapy_session_intake_agent:
  roles: [intake_structured]

22_local_activities_agent:
  roles: [research_scout]

24_candidate_initial_intake_agent:
  roles: [intake_structured]

25_candidate_update_intake_agent:
  roles: [intake_structured]

06_match_analyzer:
  roles: [psychology_relationship]

23_relationship_agent:
  roles: [psychology_relationship]

07_weekly_reset_nomad_ops_agent:
  roles: [cross_domain_orchestrator]
```

---

## 7. Сопоставление моделей между источниками

Порядок:

1. Ручная таблица aliases.
2. Exact match по canonical ID.
3. Нормализация developer + model family + version.
4. Учёт reasoning variants.
5. Fuzzy match только как кандидат.
6. Не применять fuzzy match автоматически без confidence threshold.

Нельзя автоматически объединять:

```text
model
model-high
model-xhigh
model-thinking
model-instruct
model-preview
```

Для каждой вариации хранить отдельную запись, если различаются цена, latency, reasoning effort или benchmark scores.

---

## 8. Quota management

### 8.1 Типы квот

```text
exact
estimated
unknown
```

`exact` — API отдаёт остаток и reset.

`estimated`:

```text
estimated_remaining =
configured_limit - usage_since_reset
```

`unknown` — остаток неизвестен. Применять консервативный коэффициент:

```yaml
unknown_quota_capacity_factor: 0.35
```

### 8.2 Хранимые ограничения

```text
requests_per_minute
requests_per_hour
requests_per_day
tokens_per_minute
tokens_per_day
concurrency
remaining_requests
remaining_tokens
reset_at
remaining_ratio
```

### 8.3 Защита от платного списания

Для endpoint с free quota обязательны:

- известный лимит;
- известный остаток или надёжно вычисляемый usage;
- известное время reset;
- возможность остановить routing до достижения нуля;
- safety buffer на задержку telemetry.

```yaml
quota_safety_buffer: 0.10
minimum_absolute_request_reserve: 5
disable_when_quota_unknown: true
```

Endpoint отключается заранее:

```text
effective_remaining =
  reported_remaining
  - pending_requests_estimate
  - safety_buffer
```

Если provider не позволяет гарантированно предотвратить платное списание после исчерпания free quota, такой endpoint считается `unknown_excluded`.

### 8.4 Резерв

По умолчанию:

```yaml
quota_reserve: 0.15
```

Последние 15% квоты не использовать как обычную primary capacity.

---

## 9. Защита от концентрации

Жёсткие ограничения:

```yaml
max_primary_roles_per_quota_pool: 1
max_primary_roles_per_provider_group: 2
min_provider_groups_in_top3: 2
min_quota_pools_in_top3: 2
max_projected_traffic_per_provider_group: 0.40
```

Дополнительные правила:

- критичные роли должны иметь primary из разных quota pools;
- `research_scout`, `health_reasoning` и `cross_domain_orchestrator` не должны одновременно иметь primary из одного quota pool;
- verifier/fallback по возможности должен быть из другого model family;
- один endpoint может повторяться в нескольких ролях только как fallback;
- нельзя считать `antigravity` и `agy` независимыми, если у них общий Google account/quota pool.

---

## 10. Scoring

Для каждой пары `role × provider_endpoint` рассчитывается итоговый score.

Перед scoring применяется hard filter:

```text
endpoint enabled
AND access_status IN (
  free_unlimited,
  free_quota_available,
  free_promotional_available
)
AND probe_status = passed
AND free_quota_remaining > reserve
AND can_hard_stop_at_zero = true
AND breaker_state != open
```

`free_quota_exhausted`, `free_promotional_expired`, `paid_only_excluded` и `unknown_excluded` полностью исключаются до scoring.

Пример:

```text
Role Score =
  benchmark_fit
+ capability_fit
+ health_score
+ quota_headroom
+ latency_score
+ stability_score
- concentration_penalty
- recent_failure_penalty
```

Базовые веса:

```yaml
benchmark_fit: 35
capability_fit: 15
quota_headroom: 15
health_score: 10
latency_score: 10
stability_score: 15
```

### 10.1 Benchmark fit по ролям

```yaml
routing_fast:
  intelligence: 0.10
  agentic: 0.15
  coding: 0.00
  multilingual: 0.15
  latency: 0.30
  quota_efficiency: 0.30

intake_structured:
  intelligence: 0.20
  agentic: 0.20
  multilingual: 0.20
  structured_output: 0.40

document_understanding:
  intelligence: 0.20
  vision: 0.35
  context: 0.20
  structured_output: 0.25

research_scout:
  intelligence: 0.25
  agentic: 0.25
  multilingual: 0.15
  context: 0.15
  tool_calling: 0.20

constraint_optimizer:
  intelligence: 0.30
  scientific_reasoning: 0.20
  agentic: 0.15
  structured_output: 0.20
  calculation: 0.15

admin_finance_precision:
  intelligence: 0.25
  structured_output: 0.30
  calculation: 0.20
  reliability: 0.25

health_reasoning:
  intelligence: 0.35
  scientific_reasoning: 0.30
  context: 0.15
  reliability: 0.20

psychology_relationship:
  intelligence: 0.20
  multilingual: 0.20
  context: 0.25
  language_quality: 0.20
  reliability: 0.15

cross_domain_orchestrator:
  intelligence: 0.30
  agentic: 0.25
  context: 0.25
  structured_output: 0.10
  reliability: 0.10
```

### 10.2 Concentration penalty

```text
penalty =
  primary_roles_on_quota_pool * pool_penalty
+ primary_roles_on_provider_group * provider_penalty
+ projected_load_ratio * load_penalty
```

---

## 11. Создание combo

Для каждой роли создаётся отдельный OmniRoute combo.

Пример:

```yaml
combo: role-research-scout
strategy: weighted

targets:
  - endpoint: openrouter/model-a
    weight: 50
    quota_pool: openrouter_1

  - endpoint: antigravity/model-b
    weight: 30
    quota_pool: google_1

  - endpoint: github/model-c
    weight: 20
    quota_pool: github_1
```

Стратегии:

- `weighted` — основной режим;
- `priority` — для редких дорогих ролей;
- `least-used` — для нескольких аккаунтов одного класса;
- fallback/retry выполняет OmniRoute.

---

## 12. Циклы работы

### Каждые 5 минут: `health-sync`

- получить health;
- получить circuit breaker/lockout;
- получить ошибки;
- обновить latency;
- временно выключить неработающие endpoints;
- не перестраивать все combo без необходимости.

### Каждый час: `quota-rebalance`

- получить usage;
- обновить остатки квот;
- пересчитать projected load;
- изменить веса combo;
- сохранить quota reserve;
- проверить concentration constraints.

### Каждые 30 минут: `provider-catalog-scan`

- получить актуальный список всех providers из OmniRoute;
- получить каталог моделей каждого provider;
- определить бесплатный статус каждого endpoint;
- сравнить с предыдущим snapshot;
- найти новые, исчезнувшие и ставшие платными модели;
- поставить новые и изменившиеся endpoint в очередь probe.

### Раз в сутки: `metadata-sync`

- загрузить models.dev;
- загрузить Artificial Analysis;
- обновить metadata canonical models;
- сопоставить новые endpoint;
- обновить benchmark cache.

### После каждого изменения каталога: `probe-new-models`

- отправить короткий дешёвый тестовый запрос;
- проверить обычный текстовый ответ;
- проверить structured output, если заявлен;
- проверить tool calling, если заявлен;
- измерить TTFT и total latency;
- сохранить фактический model ID из ответа;
- пометить endpoint как `passed`, `failed` или `incompatible`;
- не добавлять модель в production-combo до успешного probe.

### Раз в неделю: `model-review`

- пересчитать role scores;
- проверить хронически нестабильные endpoints;
- предложить или применить replacements;
- архивировать устаревшие модели;
- обновить benchmark cache.

---

## 13. Использование LLM

LLM используется только для задач, которые нельзя надёжно решить обычным кодом:

- классификация новой модели по ролям;
- анализ release notes;
- оценка capabilities, отсутствующих в structured sources;
- оценка результатов локальных benchmark prompts;
- предложение aliases при сложном match.

LLM вызывается через OmniRoute.

LLM возвращает только structured JSON:

```json
{
  "canonical_model": "qwen3-coder",
  "role_scores": {
    "constraint_optimizer": 0.74,
    "research_scout": 0.65
  },
  "capabilities": {
    "tool_calling": true,
    "structured_output": true,
    "vision": false
  },
  "confidence": 0.86,
  "reason": "..."
}
```

LLM не имеет права напрямую изменять OmniRoute config.

---

## 14. Применение конфигурации

Порядок:

1. Построить desired state.
2. Сравнить с текущим state.
3. Игнорировать незначительные изменения.
4. Проверить hard constraints.
5. Сохранить snapshot.
6. Обновить combo через OmniRoute API.
7. Выполнить smoke test.
8. При ошибке выполнить rollback.

Антидребезг:

```yaml
minimum_score_improvement: 0.10
minimum_weight_change: 10
promotion_stability_period_hours: 24
failure_cooldown_minutes: 60
max_changes_per_run: 10
```

---

## 15. PostgreSQL schema

Минимальные таблицы:

```text
canonical_models
provider_endpoints
provider_catalog_snapshots
quota_research_sources
quota_rules
quota_conflicts
provider_accounts
provider_groups
quota_pools
endpoint_quota_pools
model_aliases
model_capabilities
model_benchmarks
endpoint_pricing
endpoint_probes
endpoint_health
endpoint_usage
role_definitions
role_model_scores
role_assignments
combo_snapshots
change_log
sync_runs
```

### Ключевые поля

`canonical_models`:

```text
id
canonical_name
developer
family
version
status
discovered_at
updated_at
```

`provider_endpoints`:

```text
id
provider
provider_model_id
canonical_model_id
account_id
provider_group_id
quota_pool_id
pricing_status
input_price
output_price
free_quota_limit
free_quota_remaining
free_quota_reset_at
probe_status
enabled
first_seen_at
last_seen_at
removed_at
```

`endpoint_health`:

```text
endpoint_id
status
success_rate
error_rate
latency_p50
latency_p95
latency_p99
breaker_state
measured_at
```

`role_assignments`:

```text
role_id
endpoint_id
position
weight
is_primary
score
valid_from
valid_to
```

`change_log`:

```text
run_id
entity_type
entity_id
before_json
after_json
reason
created_at
```

---

## 16. CLI

```bash
free-model-orchestrator scan-providers
free-model-orchestrator research-quotas
free-model-orchestrator detect-free
free-model-orchestrator probe-models
free-model-orchestrator sync-health
free-model-orchestrator sync-quotas
free-model-orchestrator sync-metadata
free-model-orchestrator sync-benchmarks
free-model-orchestrator match-models
free-model-orchestrator score-roles
free-model-orchestrator rebalance
free-model-orchestrator apply
free-model-orchestrator rollback
free-model-orchestrator full
```

Поддержать режимы:

```bash
--dry-run
--role research_scout
--provider antigravity
--force
--verbose
```

---

## 17. Конфигурация

Пример:

```yaml
database_url: postgresql://...

omniroute:
  base_url: http://omniroute:8080
  api_key_env: OMNIROUTE_API_KEY

artificial_analysis:
  api_key_env: ARTIFICIAL_ANALYSIS_API_KEY

schedules:
  health_sync: "*/5 * * * *"
  provider_catalog_scan: "*/30 * * * *"
  quota_research: "20 2 * * *"
  quota_research_uncertain: "20 */6 * * *"
  quota_rebalance: "0 * * * *"
  metadata_sync: "15 3 * * *"
  model_review: "30 4 * * 0"

constraints:
  quota_reserve: 0.15
  max_primary_roles_per_quota_pool: 1
  max_primary_roles_per_provider_group: 2
  min_provider_groups_in_top3: 2
  min_quota_pools_in_top3: 2
  max_projected_traffic_per_provider_group: 0.40

access_policy:
  free_only: true
  allow_zero_price_models: true
  allow_models_inside_free_quota: true
  require_known_quota_remaining: true
  require_known_quota_reset: true
  require_hard_stop_at_zero: true
  exclude_paid_only_endpoints: true
  exclude_unknown_access_status: true

safety:
  dry_run_by_default: true
  max_changes_per_run: 10
  require_smoke_test: true
  auto_rollback: true
```

---

## 18. Логи и observability

Обязательно логировать:

- sync start/end;
- source fetch errors;
- новые модели;
- unmatched models;
- quota changes;
- health degradation;
- role score changes;
- combo changes;
- rejected changes;
- smoke-test failures;
- rollback.

Метрики:

```text
sync_runs_total
sync_failures_total
new_models_total
unmatched_models_total
active_endpoints
disabled_endpoints
quota_remaining_ratio
provider_error_rate
provider_latency_p95
combo_changes_total
rollback_total
```

---

## 19. Failure handling

- Ошибка интернет-поиска не должна стирать последнее подтверждённое quota rule.
- Устаревшее quota rule должно иметь TTL и статус `stale`.
- Нельзя принимать LLM-вывод о квоте без сохранённого источника.
- Сторонний источник не может автоматически повысить endpoint до production.
- Ошибка одного provider catalog не должна блокировать сканирование остальных providers.
- Endpoint должен быть исключён до следующего routing request, если free quota исчерпана, промо закончилось или доступ стал только платным.
- Неизвестная цена трактуется как небесплатная до подтверждения.
- Probe запускается только при подтверждённой бесплатной доступности и гарантии hard stop до платного списания.
- Ошибка models.dev не должна ломать health sync.
- Ошибка Artificial Analysis не должна блокировать текущие combo.
- Ошибка одного provider endpoint не должна отключать canonical model целиком.
- При отсутствии quota data использовать последний известный state.
- При невозможности безопасно применить config оставить текущую конфигурацию.
- При падении PostgreSQL не применять изменения.
- При неуспешном smoke test выполнить rollback.
- Все внешние вызовы должны иметь timeout, retry и exponential backoff.

---

## 20. Этапы реализации

### Этап 1

- PostgreSQL schema;
- получение списка всех OmniRoute providers;
- provider adapters;
- snapshots каталогов;
- определение бесплатных endpoint;
- dry-run отчёт об изменениях.

### Этап 2

- probe новых моделей;
- health и latency;
- обнаружение исчезнувших и ставших платными endpoint;
- ручные quota pools;
- автоматическое отключение неработающих моделей.

### Этап 3

- models.dev sync;
- Artificial Analysis sync;
- model matching;
- aliases;
- role definitions и scoring.

### Этап 4

- quota-aware allocation;
- concentration constraints;
- генерация и применение role-combo;
- snapshots, smoke tests и rollback.

### Этап 5

- LLM classification новых моделей;
- локальные benchmark prompts;
- observability;
- автоматическое weekly review.

---

## 21. Acceptance criteria

Сервис считается готовым, если:

1. Автоматически получает список всех зарегистрированных OmniRoute providers.
2. Обнаруживает новую бесплатную модель у Kilo или другого provider без ручного добавления.
3. Обнаруживает исчезновение модели или изменение её статуса на платный.
4. Не включает endpoint с неизвестной ценой в бесплатный production-combo.
5. Проверяет новую модель реальным probe до назначения на роль.
6. Находит модель в models.dev и создаёт или обновляет canonical record.
7. Сопоставляет canonical model с endpoint из OmniRoute.
8. Подтягивает benchmark scores Artificial Analysis.
9. Получает health и latency из OmniRoute.
10. Учитывает общую quota pool для разных provider names.
11. Не назначает один quota pool primary для всех критичных ролей.
12. Создаёт минимум два независимых бесплатных fallback для критичной роли, когда они доступны.
13. Не применяет config, нарушающий hard constraints.
14. Умеет работать в `--dry-run`.
15. Хранит snapshot до изменения.
16. Делает smoke test после изменения.
17. Выполняет rollback при ошибке.
18. Не требует участия Hermes/OpenClaw.
19. Все решения сохраняются в audit log с причиной изменения.
20. Для provider без quota API находит и сохраняет официальный источник лимитов.
21. Каждое quota rule содержит URL, дату проверки, confidence и evidence.
22. При конфликтующих источниках не применяет правило автоматически.
23. Обнаруживает изменение страницы с лимитами и запускает повторную проверку.
24. Никогда не отправляет запрос, который может выйти за пределы подтверждённой бесплатной квоты.
