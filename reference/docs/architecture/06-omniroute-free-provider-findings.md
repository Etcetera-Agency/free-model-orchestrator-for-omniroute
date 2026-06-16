
# Findings from OmniRoute free-provider code and docs

## Canonical sources inside OmniRoute

### Provider classes

Code defines:

```text
NOAUTH_PROVIDERS
OAUTH_PROVIDERS
APIKEY_PROVIDERS
WEB_COOKIE_PROVIDERS
```

Free provider selection in Free Provider Rankings currently uses:

```text
all NOAUTH_PROVIDERS
OAUTH_PROVIDERS where hasFree=true
APIKEY_PROVIDERS where hasFree=true
```

Web-cookie providers могут иметь `hasFree`, но orchestrator намеренно их не обрабатывает.
## Current no-auth examples

The examined registry includes:

```text
opencode
duckduckgo-web
theoldllm
chipotle
veoaifree-web
mimocode
```

Only LLM service kinds belong in model role combo.

## Per-model free catalog

OmniRoute exposes:

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

The catalog is more useful than a simple provider list because quotas may be shared across several models.

## Pool deduplication

OmniRoute's own total calculator counts a shared `poolKey` only once, using the maximum budget within that pool.

The orchestrator must preserve the same principle, then additionally scope the pool by account/IP/session only when the upstream quota semantics require it.

## Rankings

Free Provider Rankings joins:

```text
free provider definitions
provider registry model catalogs
Arena ELO intelligence
```

It ranks providers by top model and average score.

It omits providers without scored models, so it is a scoring source, not discovery source.

## Connection API

`GET /api/providers` returns stored provider connections and sanitizes secrets.

It does not represent the entire built-in provider registry.

Therefore:

```text
credential account count → /api/providers
built-in no-auth/free catalog → /api/free-models + registry
```


## Решение по web-cookie providers

Web-cookie providers остаются за пределами automatic model discovery, но не за пределами orchestration целиком.

```text
нет ежедневного model discovery
нет автоматического обновления model catalog
есть basic text probe
есть role scoring с uncertainty penalty
есть quota allocation при наличии usable session/quota
есть auto-combo membership только для совместимых простых ролей
```

Они считаются менее надёжной capacity и получают пониженный weight.
