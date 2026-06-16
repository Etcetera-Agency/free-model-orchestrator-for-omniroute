# Модуль 15 — Использование LLM

## Где LLM разрешена

- quota page extraction;
- сложный model alias suggestion;
- release-note capability extraction;
- qualitative evaluation response.

## Где запрещена

- расчёт remaining quota;
- выбор hard-stop threshold;
- применение combo;
- принятие решения о бесплатности без источника;
- разрешение денежного риска.

## Вызов

LLM вызывается через отдельный OmniRoute combo, который сам должен быть бесплатным и иметь quota reservation.

## Structured output

Каждая задача имеет JSON Schema.

Ответ:

1. валидируется JSON Schema;
2. проходит deterministic checks;
3. сохраняется вместе с prompt version и source IDs;
4. не применяется напрямую.

## Bootstrap problem

Если orchestrator ещё не сформировал combo для себя:

- использовать вручную заданный bootstrap endpoint;
- он обязан быть подтверждённо бесплатным;
- при недоступности перейти в режим без LLM, а не использовать платный endpoint.
