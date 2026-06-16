# Модуль 07 — Telemetry Sync

## Цель

Получать фактическую стабильность и скорость.

## OmniRoute sources

```text
GET /api/monitoring/health
GET /api/telemetry/summary
GET /api/rate-limits
GET /api/resilience
GET /api/usage/history
GET /api/usage/logs
GET /api/usage/request-logs
GET /api/usage/{connectionId}
```

## Частота

Основной sync выполняется один раз в сутки перед scoring.

Дополнительно:

- request logs читаются только для расследования;
- ручной urgent sync возможен через CLI;
- временные runtime failures между daily runs обрабатывает OmniRoute circuit breaker/fallback.

Orchestrator не обязан поддерживать real-time monitoring.

## Нормализация

### Health observation

```text
provider/account/endpoint
status
breaker_state
success_count
failure_count
error_rate
window_start
window_end
```

### Latency

OmniRoute summary может быть provider-level. Если endpoint-level нет, хранить granularity:

```text
provider
account
endpoint
```

Нельзя выдавать provider-level p95 за точную endpoint latency.

### Errors

Нормализовать:

```text
auth
quota
rate_limit
model_not_found
timeout
provider_5xx
invalid_response
content_filter
unknown
```

## Вычисления

Rolling windows:

- 15 минут;
- 1 час;
- 24 часа;
- 7 дней.

Health score:

```text
success_rate
- timeout penalty
- breaker penalty
- recent consecutive failure penalty
```

## Сохранение

Raw observations — immutable.

Aggregates — upsert по endpoint/window.

## Degradation

Endpoint получает `degraded`, если:

- 3 последовательные ошибки;
- success rate ниже threshold;
- p95 выше role threshold;
- breaker open.

Не отключать canonical model у других providers.
