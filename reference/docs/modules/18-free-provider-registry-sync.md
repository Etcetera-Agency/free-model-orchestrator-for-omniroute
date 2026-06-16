
# Модуль 18 — OmniRoute Free Provider Registry Sync

## Цель

Получить встроенный каталог бесплатных providers и моделей непосредственно из OmniRoute.

Этот модуль запускается до Account Discovery.

## Почему он нужен

`GET /api/providers` возвращает только сохранённые credential connections.

Built-in no-auth providers могут работать без connection и поэтому не обязаны присутствовать в этом ответе.

Нельзя делать вывод:

```text
provider отсутствует в /api/providers
→ provider недоступен
```

для no-auth providers.

## Основные API

### 1. Free model catalog

```http
GET /api/free-models
```

Требует management auth.

Ответ:

```json
{
  "models": [
    {
      "provider": "provider-id",
      "modelId": "model-id",
      "displayName": "Model name",
      "monthlyTokens": 1000000,
      "creditTokens": 0,
      "freeType": "recurring-daily",
      "poolKey": "provider:shared-pool",
      "tos": "caution"
    }
  ]
}
```

Поля:

```text
provider
modelId
displayName
monthlyTokens
creditTokens
freeType
poolKey
tos
```

`poolKey` означает, что несколько моделей делят одну общую квоту. Их бюджеты нельзя суммировать.

### 2. Free provider rankings

```http
GET /api/free-provider-rankings
GET /api/free-provider-rankings?category=coding
GET /api/free-provider-rankings?category=coding&limit=100
```

Ответ содержит:

```text
provider id
provider name
category = noauth|oauth|apikey
top model
Arena ELO
normalized score
confidence
average score
model count
```

Ограничение: providers без scored models могут отсутствовать. Поэтому endpoint нельзя использовать как полный каталог.

### 3. Free-tier summary

```http
GET /api/free-tier/summary
GET /api/free-tier/summary?excludeTosAvoid=1
```

Используется только для:

- контрольной суммы;
- сверки modelCount/poolCount;
- обнаружения резкого изменения каталога;
- dashboard/audit.

Нельзя использовать `remaining` из summary как точный remaining конкретного quota pool.

## Категории free providers

### No-auth

Built-in provider без пользовательского credential.

Примеры из текущего registry:

```text
opencode
duckduckgo-web
theoldllm
chipotle
mimocode
veoaifree-web
```

Для LLM-комбо включаются только providers с `serviceKinds` содержащим `llm`.

### OAuth с free tier

Provider требует OAuth account и имеет `hasFree=true`.

Capacity зависит от числа подключённых независимых accounts.

### API-key с free tier

Provider требует API key и имеет `hasFree=true`.

Capacity зависит от account/quota scope.

### Web-cookie/free session

Web-cookie providers исключены из автоматического model-refresh pipeline.

Причины:

- их модельный набор обычно не является стабильным API-каталогом;
- доступ зависит от браузерной сессии и cookie;
- автоматическое обновление моделей не даёт надёжной информации о доступных capabilities.

При этом web-cookie endpoint может участвовать в role combo, если:

- модель добавлена вручную или из статического OmniRoute registry;
- endpoint прошёл basic text probe;
- роль не требует tool calling;
- роль не требует structured output;
- роль не требует vision/audio/file API;
- роль допускает нестабильный session-based provider;
- quota/session state считается достаточным.

### Optional API key on free provider

Некоторые free providers допускают и no-auth, и API-key режим.

Не создавать две независимые quota capacity автоматически. Сначала определить, действительно ли credential создаёт отдельный quota pool.

## Алгоритм sync

### 1. Вызвать `/api/free-models`

Сохранить raw snapshot и hash.

Для каждой модели upsert:

```text
provider_id
provider_model_id
display_name
free_type
documented_monthly_tokens
documented_credit_tokens
omniroute_pool_key
tos_verdict
source = omniroute_free_models
```

### 2. Сгруппировать по `poolKey`

Если `poolKey != null`:

```text
quota_pool_template = poolKey
```

Все модели с одинаковым ключом принадлежат одной documented pool.

Если `poolKey == null`, модель может иметь независимую квоту, но это ещё нужно подтвердить provider semantics.

### 3. Вызвать rankings

Для каждой category:

```text
default
coding
review
documentation
debugging
```

Сохранить quality observations.

Не удалять provider из free registry, если он отсутствует в rankings.

### 4. Вызвать summary

Сравнить:

```text
modelCount
poolCount
steadyRecurringTokens
firstMonthRealisticTokens
```

с локально рассчитанными значениями.

При расхождении:

```text
registry_sync_status = inconsistent
```

и сохранить diagnostics.

### 5. Объединить со static/provider registry metadata

Если установленная версия OmniRoute доступна локально, дополнительно читать:

```text
NOAUTH_PROVIDERS
OAUTH_PROVIDERS entries with hasFree
APIKEY_PROVIDERS entries with hasFree
provider registry models
```

`WEB_COOKIE_PROVIDERS` не участвуют в automatic model discovery, но их вручную настроенные endpoint могут быть импортированы как static candidates.

API остаётся основным runtime contract. Чтение source code — fallback и средство диагностики версии.

## Free type

Поддержать значения OmniRoute:

```text
recurring-daily
recurring-monthly
recurring-credit
one-time-initial
keyless
discontinued
```

Правила:

- `discontinued` исключается;
- `one-time-initial` не считается постоянной daily capacity;
- `recurring-credit` учитывается отдельно;
- `keyless` не означает unlimited;
- recurring budgets могут быть shared по `poolKey`.

## ToS verdict

```text
ok
caution
ambiguous
avoid
unknown
```

Политика конфигурируется:

```yaml
tos_policy:
  allow: [ok, caution, ambiguous, unknown]
  exclude: [avoid]
```

Orchestrator не должен молча игнорировать ToS metadata OmniRoute.

## No-auth virtual instance

Для каждого доступного no-auth provider создаётся:

```text
account_type = builtin_noauth
omniroute_connection_id = null
provider_instance_key = noauth:{provider_id}:{scope_key}
```

Это не пользовательский account.

## Quota scope no-auth provider

No-auth provider может ограничивать:

```text
IP
OmniRoute installation
device fingerprint
bootstrap JWT/session
public endpoint globally
unknown
```

Поля:

```text
quota_scope_type
quota_scope_key
scope_confidence
```

Примеры scope key:

```text
ip:{egress_ip_hash}
installation:{machine_id_hash}
device:{device_fingerprint_hash}
session:{provider_session_hash}
global:{provider_id}
```

При unknown использовать один shared pool на всю OmniRoute installation.

## Сопоставление `poolKey` и accounts

### No-auth

```text
effective_pool_id =
omniroute_pool_key + quota_scope_key
```

### Credential provider, quota per account

```text
effective_pool_id =
omniroute_pool_key + upstream_account_ref
```

### Credential provider, quota global/shared

```text
effective_pool_id =
omniroute_pool_key
```

Не добавлять account suffix автоматически, пока независимость account quota не подтверждена.

## Сохранение

### free_provider_registry_snapshots

```text
run_id
omniroute_version
free_models_hash
rankings_hashes
summary_hash
raw_json
created_at
```

### free_provider_definitions

```text
provider_id
free_category
service_kinds
has_free
no_auth
free_note
source
first_seen_at
last_seen_at
```

### free_model_definitions

```text
provider_id
provider_model_id
free_type
monthly_tokens
credit_tokens
omniroute_pool_key
tos_verdict
status
```

## Ошибки

- `/api/free-models` недоступен → использовать последний snapshot, запретить добавление новых free providers;
- rankings недоступен → quality signal stale, catalog продолжает работать;
- summary недоступен → пропустить контрольную сверку;
- неизвестный `freeType` → сохранить, но исключить до обновления parser;
- provider есть в registry, но нет моделей → не добавлять в combo.

## Acceptance criteria

1. No-auth providers обнаруживаются без `/api/providers`.
2. Free OAuth/API-key providers объединяются с credential accounts.
3. `poolKey` дедуплицирует общую квоту моделей.
4. `keyless` не трактуется как unlimited.
5. `discontinued` не попадает в combo.
6. Web-cookie providers не проходят automatic model discovery, но могут попасть в combo после capability gating и basic text probe.
7. Rankings не используется как полный каталог.
8. Summary используется только для контроля.
