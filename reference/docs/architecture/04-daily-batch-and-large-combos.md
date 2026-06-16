
# Daily batch и большие combo

## Принцип

Система не пытается быть real-time control plane.

Она один раз в сутки обновляет каталог и формирует достаточно широкий набор моделей, чтобы OmniRoute мог самостоятельно пережить:

- временный 429;
- краткий outage;
- зависший endpoint;
- локальный quota exhaustion;
- circuit breaker.

## Initial candidate source

Первый фильтр — models.dev:

```text
zero input/output cost
OR "free" token in model ID/name
```

Это дешёвый способ быстро найти основную массу бесплатных моделей.

Затем список расширяется provider-specific моделями, для которых есть подтверждённая free quota.

## Размер combo

По умолчанию:

```yaml
target_size: 12
minimum_size: 4
maximum_per_quota_pool: 2
maximum_per_provider_group: 3
```

Это не означает, что одна и та же модель может без ограничений попасть во все роли.

Перед построением combo выполняется глобальное распределение quota capacity по ролям.

Модель добавляется:

- как guaranteed target, если роли выделена часть quota pool;
- как opportunistic fallback с малым весом, если capacity не гарантирована.

Если доступно меньше независимых моделей или quota недостаточно, combo создаётся в degraded mode.

## Порядок моделей

1. лучшие role score;
2. разные quota pools;
3. разные provider groups;
4. разные model families;
5. достаточная quota до следующего daily run.

## Когда нужен внеплановый rebuild

Только при существенном риске:

- обнаружено платное списание;
- provider удалён вручную;
- все модели критичной роли недоступны;
- текущий combo повреждён;
- изменился access policy.

Обычные runtime failures не являются причиной для immediate rebuild.
