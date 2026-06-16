
# Модуль 19 — Web-cookie Static Candidates

## Цель

Разрешить web-cookie providers в role combo без попытки автоматически обновлять их модельные каталоги.

## Источники endpoint

Web-cookie endpoint создаётся только из:

1. существующей OmniRoute connection;
2. static provider registry;
3. manual override;
4. ранее подтверждённой модели.

Автоматический model discovery для web-cookie запрещён.

## Обязательные поля

```text
provider_id
connection_id
manual_model_id
display_name
session_status
capabilities
last_basic_probe_at
last_success_at
quota_state
```

## Capability policy

По умолчанию web-cookie endpoint имеет:

```yaml
capabilities:
  text_chat: true
  tool_calling: false
  structured_output: false
  vision: false
  files: false
  audio: false
  streaming: unknown
```

Capability можно повысить только после отдельного подтверждённого probe.

## Допустимые роли

Web-cookie endpoint разрешён, если роль требует только:

```text
plain text input
plain text output
basic reasoning
summarization
classification without strict JSON
conversation
```

Примеры потенциально допустимых ролей:

```text
psychology_relationship
часть research_scout без tools
часть cross_domain_orchestrator без tools
routing_fast только если plain-text classification допустима
```

## Запрещённые роли

Endpoint исключается, если роль требует:

```text
tool calling
strict JSON schema
vision
document/file upload
deterministic structured extraction
function calling
low-latency SLA
high concurrency
```

Типично запрещены:

```text
intake_structured
document_understanding
admin_finance_precision
health_reasoning при structured/tool workflows
constraint_optimizer с tool usage
```

Финальное решение определяется role requirements, а не названием роли.

## Probe

### Basic text probe

Проверить:

- session valid;
- HTTP success;
- plain text response;
- latency;
- absence of login/challenge page;
- фактический model/provider, если доступно.

### Optional capability probes

Выполняются только вручную или при явном static capability claim.

## Scoring penalty

Добавить penalties:

```text
session_instability_penalty
manual_catalog_penalty
unknown_model_penalty
cookie_expiry_penalty
anti_bot_risk_penalty
```

Web-cookie endpoint не должен становиться primary при наличии сопоставимого API/no-auth endpoint.

## Weight policy

```yaml
web_cookie:
  max_weight: 10
  primary_allowed: false
  fallback_only: true
```

Primary можно разрешить manual override.

## Session health

Daily batch проверяет:

```text
cookie/session not expired
last successful request
recent auth errors
challenge/captcha state
```

Если session invalid:

```text
access_status = unavailable
```

## Quota

Если лимит неизвестен:

- endpoint может быть только opportunistic fallback;
- не учитывается как guaranteed capacity;
- weight ограничен.

Если documented/session quota известна, допускается обычный quota pool.

## Acceptance criteria

1. Web-cookie models не обновляются автоматически.
2. Manual/static endpoint может попасть в combo.
3. Tool-calling role не получает web-cookie endpoint без подтверждённой capability.
4. Strict JSON role исключает web-cookie endpoint по умолчанию.
5. Unknown quota не считается guaranteed capacity.
6. Web-cookie endpoint по умолчанию fallback-only.
