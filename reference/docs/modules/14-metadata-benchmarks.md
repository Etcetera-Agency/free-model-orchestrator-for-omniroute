# Модуль 14 — Metadata и Benchmarks

## models.dev sync — внешний источник кандидатов

Раз в сутки:

```text
GET https://models.dev/catalog.json
```

Дополнительно допускаются `api.json` и `models.json`.

Сразу после загрузки формируется `models_dev_free_candidate_set`.

Затем он объединяется с собственным каталогом OmniRoute `/api/free-models`.

OmniRoute free registry имеет приоритет для provider-specific free tiers и no-auth providers.

### Правила кандидата

```text
listed input cost = 0 AND listed output cost = 0
OR normalized model ID содержит отдельный token "free"
OR normalized display name содержит отдельное слово "free"
```

Не использовать простое substring-сравнение, чтобы не ловить случайные совпадения внутри других слов.

`listed cost` читается из provider-keyed данных models.dev (`providers[*].models[*].cost`), т.к. цена в models.dev задаётся для пары provider→model, а не для модели глобально. Верхнеуровневый список `models` в `catalog.json` поля `cost` не содержит. Отсутствие `cost` (часть open-weights/local моделей) не интерпретируется как `0`.

Каждый кандидат получает причину:

```text
zero_cost
free_in_model_id
free_in_display_name
multiple_signals
```

Сохраняется:

- raw payload hash;
- canonical models;
- provider offerings;
- capabilities;
- context/output;
- listed pricing;
- release/update dates.

Listed pricing `0` является первым сильным сигналом для кандидата, но финальное решение всё равно принимается на уровне конкретного OmniRoute provider/account.

Модель с ненулевой ценой остаётся кандидатом только если OmniRoute/provider или quota research подтверждают бесплатную квоту.

## Artificial Analysis sync

```text
GET https://artificialanalysis.ai/api/v2/language/models
x-api-key: ...
```

Сохранять response rate-limit headers:

```text
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
```

Free tier обновляется максимум раз в сутки и кэшируется.

## Benchmark versioning

Сохранять:

- index name;
- index version;
- score;
- measured_at;
- source updated_at.

Нельзя сравнивать значения разных версий индекса без normalization/flag.

## Failure

Если источник недоступен:

- сохранять последнее значение;
- пометить stale;
- не отключать endpoint;
- увеличить uncertainty penalty.


## Artificial Analysis scoring contract v1

### Поля, используемые в scoring

```json
{
  "intelligence_index": 24.5,
  "coding_index": 18.5,
  "agentic_index": 27.6,
  "median_output_tokens_per_second": 296.47,
  "median_end_to_end_seconds": 9.09
}
```

Адаптер сопоставляет их с фактическими именами полей текущего API. В `/api/v2/language/models` индексы лежат в объекте `evaluations` под именами `artificial_analysis_intelligence_index`, `artificial_analysis_coding_index`, `artificial_analysis_agentic_index`; скоростные метрики — отдельными полями (`median_output_tokens_per_second`, end-to-end latency). Внутренние короткие имена (`intelligence_index` и т.д.) — нормализованные псевдонимы scoring-слоя.

Назначение:

```text
intelligence_index
  общее качество модели

coding_index
  код, алгоритмы и технические задачи

agentic_index
  многошаговое планирование и агентные задачи

median_output_tokens_per_second
  скорость генерации; больше лучше

median_end_to_end_seconds
  полное время ответа; меньше лучше
```

Не участвуют в scoring v1:

```text
TTFT
first-answer-token latency
цена input/output/cache
стоимость выполнения benchmark
release date как показатель качества
отдельные benchmark subtotals
```

Полный ответ API сохраняется в raw snapshot, но нормализованная scoring table содержит только пять разрешённых метрик.

Обновление выполняется один раз в сутки. Данные считаются stale через 7 дней. Отсутствие AA-данных не исключает модель.
