# Модуль 02 — Provider Scanner

## Цель

Один раз в сутки получать каталоги всех зарегистрированных providers и сопоставлять их с начальным списком бесплатных кандидатов из models.dev.

## Источники

### Основные

1. `GET /api/providers`
2. для каждого provider: `GET /api/providers/{id}`
3. для каждого provider: `GET /api/providers/{id}/models`

### Контрольные

- `GET /api/models/catalog`
- `GET /v1/models`

`/v1/models` содержит также combo, поэтому он используется только как контроль видимости, а не как источник provider ownership.

## Алгоритм

### 1. Получить providers

Для каждой записи нормализовать:

```text
omniroute_provider_id
provider_type
display_name
enabled
auth_type
connection/account reference
raw_config_hash
```

Credentials не копировать.

### 2. Upsert provider/account

Ключ:

```text
omniroute_instance_id + omniroute_provider_id
```

Если provider новый:

- создать `provider`;
- создать `provider_account`;
- назначить `provider_group` и `quota_pool` из overrides или heuristic;
- поставить задачу `quota_research_required`.

### 3. Получить модели

Для каждого provider:

- вызвать `/api/providers/{id}/models`;
- передать ответ provider adapter;
- нормализовать модель;
- сохранить raw snapshot.

### 4. Snapshot

`provider_catalog_snapshots`:

```text
provider_id
catalog_hash
raw_payload
model_count
fetched_at
fetch_status
```

Если `catalog_hash` совпал с последним успешным snapshot, дальнейший diff не нужен.

### 5. Diff

Сравниваются:

- provider model ID;
- display name;
- type;
- flags;
- pricing fields;
- capabilities;
- visibility/enabled;
- raw metadata hash.

События:

```text
provider_model_added
provider_model_removed
provider_model_reappeared
provider_model_metadata_changed
provider_model_price_changed
provider_model_capability_changed
```

### 6. Приоритизация по free candidates

После catalog diff модели делятся на три группы:

```text
A. exact match с models.dev zero-cost/free candidate
B. provider model с явным free/free-tier flag
C. остальные модели
```

Группа A сразу идёт в Access Classifier.

Группа B идёт в Access Classifier и quota research.

Группа C обрабатывается только если:

- уже была активной бесплатной моделью;
- provider-specific quota rule покрывает её;
- ручной override добавил её в кандидаты.

### 7. Запись endpoint

Ключ endpoint:

```text
provider_account_id + provider_model_id + model_type
```

Новая модель:

```text
lifecycle_status = discovered
access_status = access_pending
probe_status = not_run
```

Исчезнувшая модель не удаляется:

```text
lifecycle_status = removed
removed_at = now
```

### 8. Зависимые задачи

Для added/changed:

- quota research;
- access classification;
- canonical matching;
- probe, но только после free approval.

Для removed:

- allocator rerun;
- combo diff;
- запрет новых запросов.

## Частота

- основной scan — один раз в сутки внутри daily batch;
- сразу после ручного добавления provider — опциональный event-driven запуск;
- вручную через CLI.

Постоянный 30-минутный polling не требуется.

## Защита от ложного удаления

Модель считается удалённой после:

- двух последовательных успешных catalog fetch без неё;
- с интервалом не меньше 5 минут.

Если fetch provider завершился ошибкой, отсутствующие модели не помечаются removed.
