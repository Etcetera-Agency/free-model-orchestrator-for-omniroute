
# Модуль 20 — LLM-driven Artificial Analysis Index Migration

## Цель

Обновлять role quality thresholds после изменения Artificial Analysis index с помощью сильнейшей доступной модели.

## Основной принцип

Когда версия индекса меняется:

1. система загружает новые metrics;
2. выбирает доступную модель с максимальным новым `intelligence_index`;
3. запускает отдельного migration-agent;
4. migration-agent анализирует новую шкалу и предлагает thresholds;
5. детерминированный код проверяет proposal;
6. безопасный proposal применяется.

LLM принимает смысловое решение. Код отвечает за факты, ограничения и безопасное применение.

## Выбор migration model

Кандидат должен:

```text
быть доступен через OmniRoute
пройти health check
иметь достаточное context window
поддерживать structured output или надёжный JSON
не иметь исчерпанную free quota
```

Сортировка:

```text
1. максимальный intelligence_index новой версии
2. agentic_index
3. endpoint health
4. available quota
5. latency
```

Используется конкретный endpoint, а не только canonical model.

## Fallback выбора

Если top intelligence model недоступна:

```text
взять следующую доступную модель по intelligence_index
```

Если ни одна подходящая модель недоступна:

```text
migration_status = waiting_for_model
```

Текущие thresholds и combo продолжают работать.

## Триггер

```text
fetched_index_version != active_index_version
```

Создаётся migration record.

Новая версия metrics сохраняется отдельно и не заменяет активную до rollout.

## Данные для migration-agent

В prompt передаются:

### Версии и методология

```text
old_index_version
new_index_version
available methodology notes
known composition changes
```

### Распределения

Для каждой из трёх метрик:

```text
minimum
maximum
median
P10
P25
P50
P75
P90
P95
missing rate
```

Отдельно для:

```text
всех AA-моделей
free eligible models
доступных OmniRoute endpoints
моделей в текущих combo
```

### Старые role policies

```text
role
old gate metric
old threshold
old index version
role weights
minimum context
required capabilities
```

### Operational data

```text
eligible endpoints по каждому возможному threshold
quota pools
provider groups
current combo size
minimum combo size
health
context limits
```

### Примеры моделей

Передаются top, middle и boundary models со значениями старого и нового индекса.

## Задача migration-agent

Migration-agent должен:

1. понять, как изменилась шкала;
2. решить, нужно ли менять gate metric роли;
3. выбрать новый threshold;
4. сохранить разумную сложность задач роли;
5. не разрушить бесплатную capacity;
6. объяснить каждое изменение;
7. вернуть structured proposal.

Percentile mapping показывается агенту как полезный ориентир, но не является обязательным правилом.

## Формат ответа

```json
{
  "index_version": "5.0",
  "summary": "Scale moved upward...",
  "roles": {
    "health_reasoning": {
      "metric": "intelligence_index",
      "threshold": 54,
      "reason": "Keeps advanced reasoning models...",
      "confidence": 0.88
    },
    "research_scout": {
      "metric": "agentic_index",
      "threshold": 58,
      "reason": "Requires multi-step planning...",
      "confidence": 0.84
    }
  },
  "warnings": []
}
```

Для роли разрешена только одна gate metric:

```text
intelligence_index
coding_index
agentic_index
```

## Детерминированная validation

Код не доверяет proposal без проверки.

Для каждой роли проверить:

```text
metric разрешена
threshold существует в новой шкале
eligible endpoints >= minimum_combo_size
independent quota pools достаточно
provider diversity соблюдена
minimum context соблюдён
required capabilities соблюдены
нет paid endpoint
```

Дополнительно проверить:

```text
threshold не пропускает практически все модели
threshold не оставляет роль без capacity
proposal использует именно новую index version
JSON соответствует schema
```

## Repair loop

Если proposal не проходит validation:

1. сформировать validation errors;
2. вернуть их тому же migration-agent;
3. запросить исправленный proposal;
4. повторить validation.

Максимум:

```text
3 attempts
```

После неудачи:

```text
migration_status = needs_manual_review
```

Production не меняется.

## Dry-run

После успешной validation:

```text
пересчитать role eligibility
пересчитать weighted scores
построить global allocation
построить combo diff
запустить smoke tests без production switch
```

Migration-agent может получить dry-run report и один раз скорректировать proposal, если обнаружен неожиданный operational impact.

## Approval policy

По умолчанию:

```yaml
approval_required: true
```

LLM готовит решение, но production rollout требует approval.

Можно включить auto-approval только при всех условиях:

```text
all roles status = safe
нет уменьшения independent quota pools
нет роли ниже minimum combo size
smoke tests passed
proposal confidence >= configured minimum
```

## Rollout

После approval:

1. сохранить новые threshold versions;
2. активировать new index version;
3. применить allocation plan;
4. обновить role combo;
5. выполнить production smoke test;
6. сохранить audit report.

## Rollback

При ошибке вернуть:

```text
old active index version
old thresholds
old allocation plan
old combo snapshot
```

## Использование самой сильной модели

Migration workload редкий, поэтому для него не требуется отдельная постоянная role combo.

На каждый migration run выбирается лучший доступный endpoint динамически:

```text
highest new intelligence_index
```

Это специальный system task и не расходует role quota budget без учёта. Его probe/request резервируется в orchestrator maintenance budget.

## Acceptance criteria

1. Migration decision готовит LLM.
2. Используется доступная модель с максимальным новым intelligence index.
3. Percentile mapping — только reference signal.
4. Код валидирует все operational constraints.
5. Invalid proposal возвращается LLM на repair.
6. Production не меняется при неуспешной migration.
7. Старые metrics и thresholds сохраняются.
8. Rollback полностью восстанавливает прежний plan.


## Runtime implementation

### Chosen library

Использовать:

```text
Instructor
```

Repository:

```text
567-labs/instructor
```

License:

```text
MIT
```

### Почему Instructor

Migration-agent не требует:

```text
tool loop
multi-agent graph
memory
MCP
code execution
durable workflow framework
```

Его задача одношаговая:

```text
получить migration input
→ проанализировать
→ вернуть MigrationProposal
```

Instructor уже предоставляет:

```text
Pydantic response model
structured JSON output
schema validation
automatic repair retries
provider-compatible client wrapper
```

### Не использовать

Для этой задачи не использовать:

```text
LangChain agents
CrewAI
AutoGen
PydanticAI agent runtime
smolagents
собственный agent loop
```

Они могут быть полезны для других задач, но для index migration создают лишнюю сложность.

## OpenAI-compatible integration

Migration-agent обращается к OmniRoute через стандартный OpenAI SDK:

```python
from openai import OpenAI

openai_client = OpenAI(
    base_url=OMNIROUTE_BASE_URL,
    api_key=OMNIROUTE_API_KEY,
)
```

Далее client оборачивается Instructor:

```python
import instructor

client = instructor.from_openai(
    openai_client,
    mode=instructor.Mode.JSON_SCHEMA,
)
```

Если конкретный выбранный endpoint не поддерживает native JSON Schema, adapter может использовать совместимый Instructor mode, но итог всё равно валидируется Pydantic.

## Pydantic schema

```python
from typing import Literal
from pydantic import BaseModel, Field

Metric = Literal[
    "intelligence_index",
    "coding_index",
    "agentic_index",
]

class RoleThreshold(BaseModel):
    metric: Metric
    threshold: float
    reason: str
    confidence: float = Field(ge=0, le=1)

class MigrationProposal(BaseModel):
    index_version: str
    summary: str
    roles: dict[str, RoleThreshold]
    warnings: list[str] = []
```

## Invocation

```python
proposal = client.chat.completions.create(
    model=selected_migration_model,
    response_model=MigrationProposal,
    max_retries=3,
    messages=[
        {
            "role": "system",
            "content": MIGRATION_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": migration_input_json,
        },
    ],
)
```

## Responsibility split

### Instructor

Отвечает за:

```text
schema generation
structured output
JSON parsing
Pydantic validation
repair retry after schema error
```

### Orchestrator code

Отвечает за:

```text
migration model selection
migration input construction
quota reservation
capability checks
threshold capacity validation
provider diversity validation
dry-run
approval
rollout
rollback
audit
```

Instructor не принимает operational decisions и не применяет configuration changes.

## Repair layers

Есть два разных repair слоя.

### Schema repair

Выполняет Instructor:

```text
invalid JSON
missing required field
wrong field type
unsupported enum value
confidence outside 0..1
```

### Operational repair

Выполняет Orchestrator:

```text
threshold оставил слишком мало endpoints
недостаточно independent quota pools
нарушена provider diversity
модель не поддерживает capabilities роли
```

При operational validation error Orchestrator формирует новый prompt с ошибками и повторно вызывает migration-agent.

Максимум operational repair attempts:

```text
3
```

## Dependency policy

Минимальные runtime dependencies:

```text
instructor
openai
pydantic
```

Версии должны быть pinned в lockfile.

Не использовать Instructor CLI, streaming, observability или дополнительные integrations, если они не нужны migration-agent.

## Failure policy

Если Instructor не может получить валидный `MigrationProposal`:

```text
migration_status = needs_manual_review
```

Production thresholds и combo не меняются.
