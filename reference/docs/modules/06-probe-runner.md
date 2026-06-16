# Модуль 06 — Probe Runner

## Цель

Проверить, что бесплатный endpoint реально работает и соответствует заявленным capabilities.

## Precondition

Probe разрешён только если Access Classifier вернул:

```text
free_unlimited
free_quota_available
free_promotional_available
```

И Quota Manager зарезервировал probe capacity.

## Endpoint

Предпочтительно dedicated route:

```text
POST /v1/providers/{provider}/chat/completions
```

Это исключает случайный routing на другой provider.

Model передаётся явно.

Headers:

```text
Authorization
X-OmniRoute-No-Cache: true
X-Request-Id
```

## Probe suites

### A. Basic text

Prompt требует вернуть фиксированный token.

Проверяется:

- HTTP 200;
- непустой content;
- фактический model/provider;
- latency;
- usage.

### B. Structured output

Только если capability заявлена.

Проверяется JSON Schema:

```json
{"ok": true, "value": 7}
```

### C. Tool calling

Модель должна вызвать фиктивный безопасный tool с заданными args. Tool не выполняет внешних действий.

### D. Vision

Используется маленькая локальная test image.

### E. Long-context smoke

Не полный benchmark. Проверяется умеренный payload, чтобы не съедать quota.

## Бюджет probe

Для каждого endpoint:

```text
max probes per day
max input tokens
max output tokens
quota reserve
```

Новые модели получают один basic probe. Дополнительные capability probes выполняются только при достаточной квоте.

## Сохранение

`endpoint_probes`:

```text
endpoint_id
suite_version
probe_type
request_hash
started_at
finished_at
http_status
normalized_error
ttft_ms
total_latency_ms
input_tokens
output_tokens
response_hash
passed
details_json
```

Полный пользовательский content не нужен; используются только тестовые prompts.

## Retry

- network/5xx: один retry;
- 429: не retry, передать Quota Manager;
- 401/403: endpoint auth degraded;
- 402: немедленно исключить и запустить quota research;
- invalid model: catalog stale.

## Promotion

Endpoint становится `active` только если:

- basic probe passed;
- free access всё ещё valid;
- breaker closed;
- match confidence достаточен.

## Re-probe

- после появления модели;
- после изменения model metadata;
- после reset, если endpoint долго был exhausted;
- после 3 runtime failures;
- еженедельно для active endpoint с низким traffic.


## Web-cookie probe mode

Для web-cookie provider по умолчанию выполняется только `basic_text`.

Запрещено автоматически предполагать поддержку:

```text
tools
structured output
vision
files
audio
```

Session/login HTML, captcha или challenge response считаются probe failure.


## Context-window probe

Полный бинарный поиск максимального контекста ежедневно не выполняется.

Probe запускается только если:

- context неизвестен;
- provider metadata конфликтует с models.dev;
- endpoint новый;
- runtime вернул context-length error.

Probe использует ступени:

```text
8K
16K
32K
64K
128K
256K
```

Сохраняется максимальная подтверждённая ступень.

Probe должен учитывать стоимость бесплатной квоты и выполняться только при достаточном reserve.
