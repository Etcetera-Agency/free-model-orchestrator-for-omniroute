# Модуль 05 — Model Matcher

## Цель

Связать provider-specific model ID с canonical model.

## Источники

### models.dev

- `https://models.dev/api.json`
- `https://models.dev/models.json`
- `https://models.dev/catalog.json`

`catalog.json` используется как основной combined dataset.

### Artificial Analysis

- `GET https://artificialanalysis.ai/api/v2/language/models`
- header `x-api-key`.

Free API имеет собственный лимит запросов, поэтому ответ кэшируется на сутки.

## Нормализация

Для provider model ID:

1. lowercase;
2. убрать provider prefix;
3. заменить `_` на `-`;
4. выделить lab;
5. выделить family;
6. выделить version/date;
7. выделить variants: thinking, high, instruct, preview.

## Match order

1. manual alias exact;
2. previous confirmed match;
3. exact models.dev provider model ID;
4. exact canonical slug;
5. lab + family + version;
6. constrained fuzzy candidate;
7. LLM suggestion;
8. unmatched.

## Запрещённые auto-match

Не объединять автоматически:

```text
base vs instruct
normal vs thinking
low vs high reasoning
preview vs stable
different dated snapshots
mini vs full
```

## Match confidence

```text
1.00 manual
0.98 exact provider catalog
0.95 exact slug
0.85 normalized structured match
<0.85 review_required
```

Auto-use в scoring разрешён от 0.90.

## Сохранение

`model_match_candidates` хранит все попытки.

`provider_endpoints.canonical_model_id` меняется только при accepted match.

При смене match:

- старое значение сохраняется в audit;
- probe invalidated;
- role scores invalidated.

## Metadata merge

Canonical model получает:

- context;
- max output;
- reasoning;
- vision;
- tools;
- structured output;
- release date;
- AA scores.

Provider endpoint сохраняет реальные provider-specific capabilities отдельно. Они имеют приоритет над canonical metadata.


## Provider-specific context limits

Canonical metadata не переносится на endpoint без проверки.

Для каждого endpoint сохранять отдельно:

```text
canonical_context_window
provider_context_window
effective_context_window
context_source
context_confidence

canonical_max_output_tokens
provider_max_output_tokens
effective_max_output_tokens
```

При конфликте используется меньшее подтверждённое значение.

Изменение provider context limit инвалидирует role scores и allocation.
