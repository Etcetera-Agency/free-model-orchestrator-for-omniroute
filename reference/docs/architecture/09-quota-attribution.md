
# Quota Attribution

## Цель

Связать фактический расход role combo с provider capacity даже тогда, когда OmniRoute не сообщает готовый `quota_pool`.

## Три уровня наблюдения

```text
Hermes
  requested combo
  input/output tokens
  API call count

OmniRoute
  selected endpoint
  provider
  connection/account when available
  model
  request outcome

Quota knowledge
  confirmed or inferred sharing scope
  limits
  reset behavior
```

## Quota attribution entity

Не считать `quota_pool` обязательным полем OmniRoute.

Внутри Orchestrator используется:

```text
quota_attribution_group
```

Поля:

```text
id
provider_id
scope_type
scope_key
status
source
limit_type
request_limit
token_limit
reset_rule
confidence
evidence
```

## Status

### confirmed

Независимость или совместное использование подтверждены:

```text
официальным API
OmniRoute poolKey
официальной документацией
одинаковым upstream account identifier
наблюдаемым общим remaining/reset counter
```

Только confirmed independent groups добавляют guaranteed capacity.

### inferred

Связь выведена по сильным сигналам:

```text
одинаковый credential fingerprint
одинаковый rate-limit identifier
синхронный reset
одинаковый upstream account id
стабильная correlated depletion
```

Используется для forecasting, но не как гарантированная дополнительная capacity без safety discount.

### assumed_shared

Нет достаточных данных, чтобы доказать независимость нескольких endpoint/account.

Консервативно они объединяются в один общий group.

### unknown

Неизвестны и quota scope, и sharing behavior.

Endpoint может использоваться opportunistically, но не увеличивает guaranteed capacity.

## Source priority

```text
1. Official provider quota API
2. OmniRoute explicit poolKey/quota metadata
3. Official provider documentation
4. Account/connection identifiers and credential fingerprints
5. Observed depletion/reset behavior
6. Conservative assumed_shared fallback
```

## Providers from open sources

Для provider, найденных через открытые источники, например OpenCode Free:

```text
provider может не иметь OmniRoute quota_pool
лимит может быть account-scoped, IP-scoped, installation-scoped или global
может существовать несколько аккаунтов
```

Для каждого аккаунта создаётся endpoint/account record, но capacity не суммируется автоматически.

Пример:

```yaml
provider: opencode-free
accounts:
  - account-a
  - account-b

quota_attribution:
  status: assumed_shared
  scope_type: unknown
```

После доказательства независимых counters:

```yaml
account-a:
  quota_group: opencode-account-a
  status: confirmed

account-b:
  quota_group: opencode-account-b
  status: confirmed
```

Только после этого две квоты складываются.

## No-account and no-auth providers

Для keyless/no-auth provider возможны scopes:

```text
global
IP
installation
device
session
unknown
```

IP или installation scope не следует моделировать как account capacity.

Если scope неизвестен:

```text
status = unknown
capacity_class = opportunistic
```

## Requested combo and actual usage

Hermes `state.db` используется для demand по combo:

```text
sessions.model
input_tokens
output_tokens
api_call_count
```

OmniRoute request telemetry используется для actual attribution:

```text
requested_combo
selected_endpoint
selected_connection/account
selected_model
provider
```

Затем:

```text
selected endpoint/account
→ quota attribution group
```

Если group неизвестен, usage всё равно учитывается на endpoint/provider level, но не распределяется по подтверждённым independent pools.

## Conservative capacity rule

```text
confirmed independent → full capacity
confirmed shared → one shared capacity
inferred independent → discounted/opportunistic capacity
assumed_shared → one conservative shared capacity
unknown → zero guaranteed capacity
```

Suggested default:

```text
confirmed independent: 1.00
inferred independent: 0.50
assumed_shared: 1 shared group only
unknown: 0.00 guaranteed
```

Discount влияет только на planning, а не изменяет реальный provider limit.

## Account merge and split

Если новые данные показывают, что аккаунты делят quota:

```text
merge quota attribution groups
recalculate forecast
recalculate allocation
```

Если независимость подтверждена:

```text
split group
add new confirmed capacity
recalculate allocation
```

Каждое merge/split решение сохраняет evidence и audit record.

## Acceptance criteria

1. `quota_pool` from OmniRoute is optional.
2. Open-source-discovered providers can have quota metadata.
3. Multiple accounts do not automatically multiply capacity.
4. Unknown pools cannot increase guaranteed capacity.
5. Hermes combo usage remains usable without exact pool attribution.
6. OmniRoute actual endpoint selection is mapped when available.
7. Account grouping can be revised from telemetry.
8. All grouping decisions are auditable.
