
# Модуль 17 — Account Discovery и Independent Quota Pools

## Цель

Определить, сколько credential accounts подключено к каждому OmniRoute provider и сколько из них имеют независимые бесплатные квоты.

Built-in no-auth providers обрабатывает модуль `18-free-provider-registry-sync.md`.

Простое количество строк `provider_connections` использовать нельзя.

## Основные API

### Получить provider connections

```http
GET /api/providers
```

Ожидаемые поля зависят от установленной версии OmniRoute, но модуль должен извлечь минимум:

```text
connection/provider ID
provider type
display name
auth type
active/enabled state
account reference
priority
metadata/config hash
```

### Получить состояние rate limits

```http
GET /api/rate-limits
```

Используется для сопоставления connection с:

```text
limit scope
remaining
reset
cooldown
account-level identifier
```

### Дополнительные источники

```text
GET /api/providers/{id}
GET /api/usage/{connectionId}
GET /api/usage/history
```

Они используются для уточнения account identity и фактического разделения usage.

## Результат

Для каждого provider строится:

```json
{
  "provider": "antigravity",
  "active_connections": 2,
  "independent_quota_pools": 2,
  "connections": [
    {
      "connection_id": "acc-1",
      "active": true,
      "quota_pool_id": "google-user-a",
      "quota_independence": "confirmed"
    },
    {
      "connection_id": "acc-2",
      "active": true,
      "quota_pool_id": "google-user-b",
      "quota_independence": "confirmed"
    }
  ]
}
```

## Алгоритм

### 1. Получить все connections

Вызвать:

```http
GET /api/providers
```

Для каждой записи:

- сохранить provider type;
- сохранить connection ID;
- определить active/enabled;
- сохранить auth type;
- сохранить account metadata без secrets;
- вычислить `connection_fingerprint`.

### 2. Исключить неактивные

Не учитывать:

```text
disabled
deleted
auth failed permanently
manual excluded
```

Неактивные connections сохраняются в БД, но не участвуют в capacity.

### 3. Объединить с Free Provider Registry

Только для OAuth/API-key provider:

- найти matching free provider definition;
- подтвердить, что connection использует free tier;
- создать account-specific effective pool только при доказанной независимой квоте.

No-auth providers сюда не добавляются.

Web-cookie providers также не добавляются: они вне automatic model orchestration.

### 4. Сопоставить connection с quota pool

Порядок определения:

1. ручной override;
2. явный upstream account ID из provider metadata;
3. account-level ID из rate-limit API;
4. одинаковый credential fingerprint;
5. одинаковый usage bucket/reset behavior;
6. provider-specific adapter;
7. conservative fallback: считать connections общим quota pool.

Если независимость не доказана, connections объединяются.

### 5. Определить независимость квот

Статусы:

```text
confirmed_independent
confirmed_shared
assumed_shared
unknown_shared
```

Только `confirmed_independent` создаёт дополнительную capacity.

### 6. Сравнить с предыдущим состоянием

События:

```text
account_added
account_removed
account_disabled
quota_pool_split
quota_pool_merged
account_independence_changed
no_auth_provider_added
```

При `quota_pool_merged` требуется немедленный пересчёт allocation, потому что ранее capacity могла быть завышена.

## Capacity calculation

Неправильно:

```text
provider capacity =
number_of_connections × quota_per_account
```

Правильно:

```text
provider capacity =
sum(usable capacity of independent quota pools)
```

Примеры:

### Независимые аккаунты

```text
3 accounts
100 requests/day каждый
3 independent quota pools
итого 300 requests/day
```

### Общий upstream account

```text
3 OmniRoute connections
1 upstream account
1 quota pool
итого 100 requests/day
```

### No-auth provider

No-auth capacity рассчитывается Free Provider Registry Sync:

```text
0 credential connections
1 builtin no-auth provider instance
1 или несколько poolKey, дедуплицированных по quota scope
```

## Connection fingerprint

Можно использовать только безопасные признаки:

```text
provider type
auth type
non-secret account ID
credential metadata hash
upstream tenant/project ID
```

Нельзя сохранять API keys, OAuth tokens или cookies.

## Сохранение

### provider_accounts

```text
id
provider_id
omniroute_connection_id
account_type
active
connection_fingerprint
upstream_account_ref
quota_independence_status
quota_pool_id
first_seen_at
last_seen_at
```

### quota_pool_members

```text
quota_pool_id
provider_account_id
membership_reason
confidence
valid_from
valid_until
```

### account_discovery_snapshots

```text
run_id
raw_provider_count
active_connection_count
virtual_account_count
independent_quota_pool_count
snapshot_json
created_at
```

## Частота

Один раз в сутки внутри daily batch.

Дополнительно:

- после добавления/удаления provider account;
- после изменения credentials;
- после обнаружения неожиданного общего rate limit;
- вручную через CLI.

## Ошибки

- `/api/providers` недоступен → запрещён allocation/apply;
- `/api/rate-limits` недоступен → использовать последнее подтверждённое grouping;
- новый connection без доказанной независимости → добавить в существующий shared pool;
- противоречивые данные → `unknown_shared`.

## Acceptance criteria

1. Активные connections считаются отдельно от independent quota pools.
2. Два credentials одного upstream account не увеличивают capacity.
3. Два подтверждённо независимых аккаунта увеличивают capacity.
4. No-auth provider не обязан иметь connection и не считается отсутствующим.
5. Неизвестная независимость трактуется консервативно как shared.
6. Изменение grouping запускает повторный global allocation.
