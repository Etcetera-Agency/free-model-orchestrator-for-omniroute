
# Модуль 22 — Smart Combo Reviewer

## Цель

После детерминированной сборки role combo выполнить один смысловой review готового результата.

Reviewer не рассчитывает quota и не строит allocation с нуля.

Он получает:

```text
current production combos
new calculated combos
role requirements
demand forecast
quota attribution summary
provider/account diversity
deterministic validation report
```

И может предложить небольшой diff к спискам endpoint.

## Position in pipeline

```text
candidate discovery
→ deterministic filtering
→ demand and quota allocation
→ build ordered role combos
→ deterministic validation
→ optional smart combo review
→ validate proposed diffs
→ dry-run
→ apply
```

## Runtime

Использовать тот же thin runtime:

```text
OpenAI SDK
→ OmniRoute
→ strongest available compatible model
→ Instructor
→ Pydantic ComboReview
```

Отдельный agent framework не используется.

## Combo routing strategy

Все combo, управляемые Free Model Orchestrator, создаются как:

```text
strategy = priority
```

Порядок endpoint означает:

```text
первый endpoint — основной
следующие endpoint — fallback chain
```

Не использовать:

```text
weighted routing
endpoint weights
round-robin
random
auto strategy
```

Reviewer не имеет права менять routing strategy.

## Allowed diff operations

Поддерживаются только три операции:

```text
add
remove
move
```

### Add

Добавить eligible endpoint в combo.

```json
{
  "op": "add",
  "role": "research_scout",
  "endpoint_id": "provider/account/model",
  "position": 4,
  "reason": "Добавляет отдельного provider и снижает концентрацию"
}
```

Validation:

```text
endpoint существует
endpoint бесплатный
capabilities подходят
minimum context выполнен
minimum quality gate выполнен
endpoint не запрещён policy
quota assumptions не становятся хуже
position находится в допустимом диапазоне
```

### Remove

Удалить endpoint из combo.

```json
{
  "op": "remove",
  "role": "health_reasoning",
  "endpoint_id": "provider/account/model",
  "reason": "Вероятно делит quota с уже присутствующим endpoint"
}
```

Validation после удаления:

```text
combo не пустой
minimum combo size не нарушен, кроме явно допустимого degraded mode
protected demand остаётся покрытым
provider diversity не становится ниже обязательного минимума
critical role не теряет confirmed capacity
```

### Move

Изменить позицию endpoint в ordered fallback chain.

```json
{
  "op": "move",
  "role": "fetch",
  "endpoint_id": "provider/model",
  "position": 7,
  "reason": "Quota attribution неизвестна, endpoint лучше использовать позже"
}
```

Move не меняет состав combo.

Validation:

```text
endpoint уже присутствует
position валидна
первичный endpoint после move остаётся eligible
critical role не получает unknown-only primary
```

## Reviewer output schema

```python
from typing import Literal
from pydantic import BaseModel

class ComboDiff(BaseModel):
    op: Literal["add", "remove", "move"]
    role: str
    endpoint_id: str
    position: int | None = None
    reason: str

class ComboReview(BaseModel):
    summary: str
    diffs: list[ComboDiff]
```

Пустой список означает:

```text
исходные combo можно применять без изменений
```

## Applying diffs

Orchestrator:

```text
копирует рассчитанные combo
→ применяет diff по одному
→ после каждого diff запускает deterministic validation
```

Если конкретный diff невалиден:

```text
игнорировать только этот diff
записать rejection reason в audit
продолжить проверку остальных diff
```

Reviewer не получает второй repair loop.

После обработки всех diff выполняются:

```text
full combo validation
local dry-run
apply
```

## Forbidden changes

Reviewer не может менять:

```text
routing strategy
endpoint weight
quota limit
quota attribution status
free/paid classification
provider/account identity
model quality metrics
quality gate
capabilities
context limits
historical demand
20% historical reserve
cold-start bootstrap profile
role definition
credentials
provider configuration
```

Reviewer не может создавать новый endpoint, которого нет в candidate registry.

## When review runs

Review не обязателен для каждого no-op rebuild.

Запускать:

```text
первый production build
cold start
новый provider или account
изменение quota attribution grouping
изменение agent schedule или demand profile
переход bootstrap → representative history
существенное изменение состава combo
потеря confirmed capacity критичной роли
наличие unknown/inferred quota attribution
```

Configurable trigger:

```text
combo_change_ratio >= 0.25
```

Небольшие изменения могут применяться без LLM review после обычной deterministic validation.

## Model selection

Использовать наиболее сильный доступный endpoint по:

```text
intelligence_index
```

Требования reviewer model:

```text
structured output compatible
достаточный context
free capacity available
не относится к combo, который прямо сейчас меняется, если это создаёт circular operational risk
```

Если reviewer model недоступна:

```text
review_status = skipped_no_model
```

Детерминированный combo остаётся применимым.

## Failure policy

Если structured output не получен:

```text
review_status = failed
apply deterministic combo without reviewer diffs
```

Если все diffs отклонены validation:

```text
review_status = no_valid_diffs
apply deterministic combo
```

Reviewer является advisory layer и не должен блокировать безопасный deterministic plan.

## Audit

Сохранять:

```text
review model
review model endpoint
prompt hash
input plan hash
raw structured review
accepted diffs
rejected diffs
rejection reasons
final combo hash
```

## Acceptance criteria

1. Reviewer receives already-built combos.
2. Reviewer performs one structured call.
3. Only add/remove/move are accepted.
4. Weights are not present.
5. Routing strategy is fixed to priority.
6. Each diff is validated independently.
7. Invalid diff does not invalidate other diffs.
8. Reviewer failure does not block deterministic plan.
9. Final combo passes full validation and local dry-run.
10. All accepted and rejected diffs are auditable.


## No upstream test

Smart review does not trigger `/api/combos/test`.

Accepted diffs are checked locally. Runtime endpoint failures are handled by OmniRoute fallback/circuit breaker and later telemetry-driven reconciliation.
