# Модуль 04 — Free Access Classifier

## Цель

Определить, можно ли использовать конкретный endpoint без денежных списаний прямо сейчас.

## Входные observations

1. `GET /api/pricing`
2. provider model metadata;
3. `/api/rate-limits`;
4. активный quota rule;
5. provider adapter live quota;
6. manual overrides;
7. promo expiration;
8. account type.

## Порядок принятия решения

### Шаг 1. Availability

Если provider/model disabled, removed или breaker permanently disabled:

```text
unavailable
```

### Шаг 2. Zero price

Если input/output price подтверждённо 0 и нет иных платных компонентов:

```text
free_unlimited
```

При этом rate limit всё равно сохраняется, но это не денежная quota.

### Шаг 3. Free quota

Если list price > 0, но есть валидный quota rule и live remaining:

```text
free_quota_available
```

Обязательные условия:

- known limit;
- known remaining или надёжный локальный counter;
- known reset;
- hard stop возможен;
- safety buffer не исчерпан.

### Шаг 4. Promotion

Если есть effective_to:

```text
free_promotional_available
```

После effective_to:

```text
free_promotional_expired
```

### Шаг 5. Exclusion

```text
paid_only_excluded
unknown_excluded
free_quota_exhausted
```

## Источники и trust order

```text
manual deny
> live provider quota API
> OmniRoute rate-limit state
> official active quota rule
> explicit zero pricing
> provider flag
> models.dev price
```

models.dev не доказывает бесплатность конкретного account.

## Результат

`endpoint_access_states`:

```text
endpoint_id
status
reason_code
quota_rule_id
effective_remaining
reset_at
hard_stop_capable
evidence_json
classified_at
valid_until
```

## Повторная классификация

Запускается при:

- catalog diff;
- quota refresh;
- source rule change;
- usage update;
- 402/429;
- reset;
- manual override.

## Fail closed

При schema error, stale evidence или неизвестном remaining:

```text
unknown_excluded
```
