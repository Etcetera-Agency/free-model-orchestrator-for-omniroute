
# Минимальное контекстное окно роли

## Проблема

Одна canonical model может иметь разные ограничения у разных providers:

```text
provider A: 128K context
provider B: 64K context
provider C: 32K context
```

Поэтому context window определяется на уровне конкретного `provider_endpoint`.

## Основные поля endpoint

```text
advertised_context_window
provider_context_window
probed_context_window
effective_context_window

advertised_max_output_tokens
provider_max_output_tokens
probed_max_output_tokens
effective_max_output_tokens
```

## Расчёт effective context

```text
effective_context_window =
min(
  canonical model context, если известно,
  provider catalog context, если известно,
  provider connection override, если есть,
  verified probe limit, если есть,
  OmniRoute route/model limit, если есть
)
```

Неизвестные значения не участвуют в `min`, но снижают confidence.

Если нет ни одного надёжного значения:

```text
context_status = unknown
```

## Единственный параметр роли

Каждая роль имеет только:

```text
minimum_context_window
```

Правило допуска:

```text
effective_context_window >= role.minimum_context_window
```

Если условие не выполнено, endpoint не попадает в combo роли.

## Один combo на роль

Для каждой роли создаётся один combo.

Не создаются:

```text
role.medium
role.large
role.xlarge
```

Не используются:

```text
preferred_context_window
context buckets
context similarity ratio
```

Модель с контекстом значительно больше minimum допускается без штрафа и без выделения отдельного combo.

## Пример

```yaml
research_scout:
  minimum_context_window: 64000
```

Подходят:

```text
64K
128K
256K
1M
```

Не подходят:

```text
32K
16K
```

## Request fit

Во время routing OmniRoute всё равно должен проверять фактический размер запроса:

```text
estimated_input_tokens
+ reserved_output_tokens
+ tool/schema overhead
<= effective_context_window × context_safety_factor
```

Рекомендуемый safety factor:

```text
0.90
```

Но Orchestrator не создаёт отдельные combo по размеру запроса.

## Unknown context

Endpoint с неизвестным context:

- не допускается в роль с обязательным minimum;
- может быть разрешён только explicit manual override;
- получает context probe при наличии достаточного probe reserve.

## Max output tokens

Input context и output limit — разные ограничения.

Дополнительно проверяется:

```text
effective_max_output_tokens >= role.minimum_output_tokens
```

## Acceptance criteria

1. Context определяется на уровне provider endpoint.
2. Provider-specific limit может уменьшить canonical context.
3. У роли только `minimum_context_window`.
4. Для роли создаётся один combo.
5. Endpoint ниже minimum исключается.
6. Endpoint значительно выше minimum допускается.
7. Output-token limit проверяется отдельно.
