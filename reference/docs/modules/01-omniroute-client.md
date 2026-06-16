# Модуль 01 — OmniRoute Client

## Назначение

Единый HTTP-клиент для всех вызовов OmniRoute. Остальные модули не обращаются к OmniRoute напрямую.

## Используемые API

Подтверждённые официальной документацией:

```text
GET  /api/providers
GET  /api/free-models
GET  /api/free-provider-rankings
GET  /api/free-tier/summary
GET  /api/providers/{id}
GET  /api/rate-limits
GET  /api/providers/{id}/models
POST /api/providers/{id}/test
GET  /api/models/catalog
GET  /api/pricing
GET  /api/rate-limits
GET  /api/rate-limit
GET  /api/monitoring/health
GET  /api/telemetry/summary
GET  /api/usage/history
GET  /api/usage/logs
GET  /api/usage/request-logs
GET  /api/usage/{connectionId}
GET  /api/usage/budget
GET  /api/resilience
GET  /api/combos...
GET  /api/evals
POST /api/evals
GET  /api/compliance/audit-log
GET  /v1/models
POST /v1/providers/{provider}/chat/completions
```

Точные формы `/api/combos*` должны быть зафиксированы integration fixture из установленной версии OmniRoute до реализации writer-части.

## Входы

- `OMNIROUTE_BASE_URL`
- management auth/cookie или API key;
- timeout;
- retry policy;
- установленная версия OmniRoute.

## Поведение

### Request wrapper

Каждый вызов:

1. добавляет auth;
2. ставит connect/read timeout;
3. генерирует `X-Request-Id`;
4. логирует method/path/status/duration;
5. сохраняет sanitized response при ошибке;
6. повторяет только idempotent GET;
7. не повторяет POST apply без idempotency protection.

### Version handshake

При старте:

1. вызвать health/system endpoint;
2. сохранить OmniRoute version;
3. проверить compatibility matrix;
4. если версия неизвестна — разрешить read-only, запретить apply.

## Сохранение

Сырые ответы кладутся в `external_api_observations`:

```text
source = omniroute
endpoint
request_hash
http_status
response_headers_json
response_body_json
fetched_at
expires_at
```

Секреты, bearer tokens и cookies никогда не сохраняются.

## Ошибки

- `401/403` → run failed, никаких apply.
- `404` для необязательного endpoint → capability отсутствует.
- `429` → учитывать Retry-After.
- `5xx` → retry с jitter, затем stale data.
- schema mismatch → сохранить raw payload и остановить только зависимый модуль.

## Acceptance

- Все OmniRoute-вызовы проходят через этот клиент.
- Можно записать fixtures и повторить parsing без живого OmniRoute.
- Read-only режим работает при неизвестной версии.
