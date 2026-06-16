# Provider Adapter Contract

Некоторые providers отдают каталог и quota через OmniRoute полностью, другие требуют нативный API или web extraction.

## Интерфейс

```python
class ProviderAdapter(Protocol):
    provider_type: str

    async def discover_models(
        self,
        provider_record: ProviderRecord
    ) -> list[RawProviderModel]: ...

    async def fetch_live_quota(
        self,
        account: ProviderAccount
    ) -> QuotaObservation | None: ...

    async def fetch_pricing(
        self,
        provider_record: ProviderRecord
    ) -> list[PricingObservation]: ...

    async def safe_probe_allowed(
        self,
        endpoint: ProviderEndpoint,
        quota_state: EffectiveQuotaState
    ) -> bool: ...

    async def normalize_error(
        self,
        response_status: int,
        response_body: str,
        headers: dict[str, str]
    ) -> NormalizedProviderError: ...
```

## Built-in no-auth adapter

Для no-auth provider adapter получает provider/model definitions из Free Provider Registry Sync, а не из credential connections.

Он обязан определить:

```text
quota scope
session/bootstrap identity
rate-limit error format
whether optional API key creates independent capacity
```

## Default credential adapter

Использует OmniRoute:

- `GET /api/providers/{id}/models`
- `GET /api/pricing`
- `GET /api/rate-limits`
- `GET /api/usage/{connectionId}`
- dedicated provider route для probe.

## Provider-specific adapter

Создаётся, если:

- OmniRoute не возвращает полный динамический каталог;
- quota видна только в provider dashboard/API;
- reset policy специфична;
- ошибка quota имеет нестандартный формат;
- несколько OmniRoute provider names используют общий quota pool.

## Результат discover_models

```json
{
  "provider_model_id": "model/name",
  "display_name": "Model Name",
  "type": "chat",
  "raw_pricing": null,
  "flags": ["free"],
  "capabilities": {
    "vision": false,
    "tools": true,
    "structured_output": true
  },
  "raw_payload": {}
}
```

## Правило безопасности

Adapter не имеет права объявить endpoint бесплатным только потому, что модель названа `free`. Он возвращает observations. Финальное решение принимает Access Classifier.
