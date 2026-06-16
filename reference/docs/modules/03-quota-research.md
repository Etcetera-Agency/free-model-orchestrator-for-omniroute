# Модуль 03 — Internet Quota Research (Instructor-based Quota Inspector)

## Зачем нужен и почему он основной, а не вспомогательный

OmniRoute отдаёт **подтверждённую** квоту только для ограниченного подмножества
провайдеров: те, что присутствуют в free registry с `poolKey`/documented budget
(`/api/free-models`) и/или возвращают живые счётчики через `/api/rate-limits`.
Для большинства остальных endpoint точная бесплатная ёмкость в OmniRoute
неизвестна. Поскольку главный инвариант запрещает выходить за пределы
подтверждённой бесплатной ёмкости, **этот модуль — основной способ получить
квоту для всех endpoint, по которым её не дал ни official quota API, ни
OmniRoute** (см. `quota_attribution.source_priority` в конфиге: official_quota_api
→ omniroute_pool_key → official_documentation → ...; official_documentation и
есть выход этого модуля).

Принцип работы — «инспектор»: **сначала целевой веб-поиск, чтобы найти актуальные
данные по квоте, затем извлечение через Instructor и запись результата в нашу БД**
(`quota_source_snapshots` + `quota_rules`). До поиска и записи правило не
считается существующим.

## Цель

Дополнять models.dev и OmniRoute там, где подтверждённой квоты нет или она устарела:

- модель имеет обычную платную цену, но provider даёт free quota;
- в названии есть `free`, но условия неясны;
- provider-specific каталог не совпадает с models.dev;
- изменились условия ранее известной бесплатной квоты;
- endpoint вообще не покрыт OmniRoute free registry / rate-limits.

Модуль не должен ежедневно искать интернет по каждой zero-cost модели, если
бесплатность уже однозначно подтверждена official quota API или OmniRoute и
правило не устарело.

## Входы

Из БД:

```text
provider_type
provider aliases
account_type
auth_type
provider model IDs
официальные домены
предыдущие quota rules
последние HTTP 402/429/quota errors
```

## Внешние компоненты

### SearchAdapter — OmniRoute `POST /v1/search`

Используется встроенный поиск OmniRoute через тот же gateway/auth, что и
остальные вызовы (`OMNIROUTE_URL` + API key, путь `/v1/search`). Провайдер
зафиксирован — `gemini-grounded-search` (Gemini + Google Search grounding): он
возвращает AI-суммаризацию в поле `answer.text`, а в `results[]` — список
grounding-источников (только title/url; `snippet` дублирует summary, тела
страниц там нет). Fallback не используется.

Запрос:

```json
{
  "query": "...",
  "provider": "gemini-grounded-search",
  "search_type": "web",
  "max_results": 10,
  "time_range": "month"
}
```

Ответ (форма OmniRoute):

```json
{
  "provider": "gemini-grounded-search",
  "query": "...",
  "answer": { "source": "gemini-grounded-search", "text": "<AI summary>", "model": "gemini-2.5-flash" },
  "results": [
    { "title": "...", "url": "...", "snippet": "<= answer.text>" }
  ],
  "usage": {...}, "metrics": {...}
}
```

Ничего дополнительно фетчить не нужно: вся суммаризация лежит в `answer.text`,
а `results[]` дают список процитированных URL для evidence.

Как используется ответ:

- `answer.text` — **источник, из которого Instructor извлекает квоту**;
  активируется прямо из него, официальная страница не обязательна;
- `answer.text` + `results[]` (URL) сохраняются как immutable snapshot
  (`source_type = 'search_summary'`, `source_url` = запрос), служат evidence;
- риск ограничивается **капом confidence** (`summary_confidence_cap`) и safety
  reserve из `access_policy`; такие правила получают `activated_by = summary` и
  opportunistic capacity class;
- если среди `results` есть официальный домен (`prefer_cited_source_when_present`)
  — это лишь повышает потолок confidence; отдельного fetch всё равно нет.

### PageFetcher — не используется

Отдельный fetcher не нужен: суммаризация приходит в `answer.text` из
`/v1/search`. Если в редком случае понадобится дочитать конкретную
процитированную страницу, это делается web-fetch'ем OmniRoute (Jina reader) по
тому же gateway — но в штатном потоке этот шаг отсутствует.

### LLMExtractor (Instructor)

Тот же runtime, что у migration-agent и smart-combo-reviewer: `Instructor`
поверх OpenAI-compatible API OmniRoute. Отдельный agent framework не
используется.

```text
OpenAI SDK → OmniRoute → выбранная модель → Instructor
→ Pydantic QuotaClaim → детерминированный validator
```

Вызывается **только на уже полученном тексте страницы** (никогда на snippet
поисковика). Instructor отвечает за structured output, Pydantic-валидацию и
repair retries (бюджет берётся из того же `schema_retries`/`max_repair_attempts`,
что и прочие LLM-модули). LLM не является источником истины — он лишь извлекает
факты из конкретного official источника, который сохранён как immutable snapshot.

## Построение запросов

Запросы — натурально-языковые и привязаны к текущей дате (Google summary лучше
отвечает на такие, а `freshness_days` отсекает устаревшее). Дата подставляется
из текущего run, а не хардкодится.

```text
"информация о квотах {provider} на сегодня"
"{provider} бесплатные лимиты на сегодня"
"{provider} free tier quota today"
"{provider} free models requests per day {YYYY}"
"{provider} free tier limits changelog {YYYY-MM}"
"{provider_model_id} free quota today"
```

Фоллбэк-набор ключевых запросов остаётся для провайдеров, по которым summary
пустой или без официальных цитат:

```text
"{provider} free tier API limits"
"{provider} model quota reset"
"{provider} pricing free models"
```

Отдельные aliases обязательны:

```text
Kilo
Kilo Code
OpenCode Free
MiMoCode Free
Antigravity
AGY
```

## Приоритет источников

1. официальный API docs;
2. официальный pricing/free-tier;
3. официальный dashboard/help center;
4. официальный changelog;
5. официальный GitHub;
6. официальное announcement/community;
7. сторонний источник — только clue.

## Pipeline

### 1. Search

- выполнить queries через `POST /v1/search` (provider `gemini-grounded-search`);
- взять `answer.text` (AI summary) — основной и единственный контент;
- из `results[]` взять `url` для evidence/классификации домена;
- дедуплицировать URL, удалить tracking params;
- вычислить SHA-256 и сохранить immutable snapshot
  (`source_type = 'search_summary'`, `source_url` = запрос; в payload — `answer`
  и `results`).

### 2. Fetch — не выполняется

Отдельного сетевого fetch нет: суммаризация целиком в `answer.text`. Дополнительный
HTTP-запрос не делается.

### 3. Извлечение (Instructor)

Instructor получает на вход `answer.text`:

- provider;
- model ID;
- URL или поисковый запрос;
- title;
- published/updated dates;
- нормализованный текст (страница или summary).

Ожидаемый JSON:

```json
{
  "scope": {
    "provider": "kilo",
    "account_type": "free",
    "model_patterns": ["*"]
  },
  "access_type": "free_quota",
  "limits": [
    {
      "metric": "requests",
      "amount": 100,
      "window": "day"
    }
  ],
  "reset_policy": {
    "type": "calendar",
    "timezone": "UTC"
  },
  "hard_stop": "confirmed",
  "conditions": [],
  "effective_from": null,
  "effective_to": null,
  "evidence_quotes": []
}
```

### 4. Deterministic validation

Без LLM проверить:

- amount > 0;
- metric из enum;
- window из enum;
- evidence присутствует (цитата из summary или страницы);
- model pattern подходит endpoint;
- даты не истекли;
- если источник = summary → confidence ≤ `summary_confidence_cap`,
  capacity class = opportunistic, `activated_by = summary`;
- если источник = официальная страница → confidence может быть выше.

Официальность источника больше не является условием активации — она лишь
повышает потолок confidence.

### 5. Conflict resolution

Правила считаются конфликтующими, если для одного scope отличаются:

- limit;
- window;
- reset timezone;
- eligible models;
- hard-stop policy.

Побеждает:

1. вручную подтверждённый override;
2. более специфичный scope;
3. источник с большей confidence (официальная страница > summary);
4. более новый документ/summary;
5. API/dashboard над marketing page.

При неразрешимом конфликте:

```text
quota_rule_status = conflicting
endpoint access = unknown_excluded
```

### 6. Activation

Активное правило записывается с:

```text
valid_from
valid_until
source_snapshot_id
confidence
activated_by = automatic|summary|manual
rule_hash
```

Старое правило становится `superseded`.

## Переобход

- в daily batch: только новые, изменившиеся, stale и неоднозначные записи;
- новый provider: при ближайшем daily batch или ручном запуске;
- active rule: перепроверять по TTL, обычно раз в 7 дней;
- promo с близким окончанием: ежедневно;
- stale/conflicting: ежедневно;
- 402/429: сохранить событие и обработать в следующем daily batch либо ручным urgent run.

Постоянный шестичасовой интернет-поиск не требуется.

## Change detection

Если source hash изменился:

1. не заменять правило сразу;
2. создать новую extraction;
3. сравнить parsed JSON;
4. если quota ухудшилась — немедленно перевести endpoint в safe mode;
5. если улучшилась — применить только после validation.

## Что сохраняется

- search queries;
- search results;
- source snapshots;
- parsed claims;
- conflicts;
- active quota rules;
- manual decisions.

## Что запрещено

- активировать правило вообще без evidence (ни summary, ни страницы);
- активировать summary-правило с confidence выше `summary_confidence_cap`;
- выполнять probe, чтобы “проверить”, не списываются ли деньги.

> Google AI summary как источник — разрешён (официальная страница не
> обязательна). Риск контролируется capped confidence, opportunistic capacity
> class и safety reserve из `access_policy`.
