# Test Plan

## Unit tests

### Provider Scanner

- новый provider;
- новый model ID;
- metadata change;
- один failed fetch не удаляет модели;
- удаление только после двух успешных snapshots.

### Quota Research

- official source parsed;
- third-party source не активируется;
- source hash change;
- conflicting limits;
- expired promo;
- missing hard stop.

### Access Classifier

- zero price;
- paid list price + free quota;
- exhausted quota;
- unknown remaining;
- stale rule;
- manual deny.

### Quota Manager

- reservation concurrency;
- pending requests;
- reset timezone;
- rolling window;
- 429 RPM vs daily exhaustion;
- safety buffer.

### Matcher

- exact;
- aliases;
- thinking vs normal;
- preview vs stable;
- low-confidence rejection.

### Allocator

- один quota pool не получает все primary;
- критичные роли разведены;
- fallback независим;
- недостаток моделей → degraded;
- quota forecast ограничивает weights.

### Applier

- no-op diff;
- apply;
- read-after-write mismatch;
- smoke fail rollback;
- external drift.

## Integration tests

Использовать записанные OmniRoute fixtures:

- providers;
- provider models;
- pricing;
- rate limits;
- telemetry;
- usage;
- combos.

Поднять test PostgreSQL.

HTTP calls через mock server.

## End-to-end scenarios

### models.dev добавил zero-cost/free модель, доступную у Kilo

1. daily models.dev sync добавляет модель в `free_candidate_set`;
2. provider scan находит соответствующий Kilo endpoint;
3. access classifier подтверждает zero-cost или quota research подтверждает free access;
3. matcher связывает canonical model;
4. probe проходит;
5. scorer назначает роли;
6. allocator добавляет endpoint;
7. combo diff применён;
8. audit содержит полный путь решения.

### Модель стала платной

1. pricing/source изменился;
2. access classifier исключил endpoint;
3. reservations запрещены;
4. allocator выбрал замену;
5. combo обновлён до следующего production request.

### Общая квота AGY/Antigravity

1. оба endpoint принадлежат одному quota pool;
2. usage одного уменьшает remaining обоих;
3. allocator не считает их независимыми fallback.

### Нет точной quota

1. research не находит официальный limit/hard stop;
2. endpoint получает unknown_excluded;
3. probe не выполняется;
4. платный request невозможен.

## Acceptance criteria

1. Все providers берутся из OmniRoute автоматически.
2. Динамические изменения каталогов обнаруживаются.
3. Бесплатность определяется на уровне account+endpoint.
4. Платная list-price модель допускается только внутри подтверждённой free quota.
5. Нет request при неизвестной или исчерпанной quota.
6. Каждый quota rule имеет источник и snapshot.
7. LLM output не применяется без deterministic validation.
8. Все новые endpoint проходят probe.
9. Quota pools учитывают общие upstream limits.
10. Все combo изменения имеют snapshot и rollback.

## Daily scheduling tests

- один daily run выполняет полный pipeline;
- повторный cron не запускает параллельный run;
- неизменившийся endpoint не проходит повторный probe;
- unchanged combo не вызывает write API;
- role combo содержит расширенный набор моделей;
- временная runtime ошибка одной модели не требует немедленного rebuild.


## Global quota allocation tests

- один quota pool не получает guaranteed allocation для нескольких тяжёлых ролей;
- одна модель может быть в нескольких combo только при достаточной общей capacity;
- opportunistic fallback имеет ограниченный weight;
- сумма guaranteed + expected opportunistic usage не превышает usable quota;
- oversubscribed plan не применяется;
- при нехватке quota менее критичная роль переводится в degraded mode;
- большой combo не считается достаточным, если все модели используют один общий quota pool;
- AGY и Antigravity с общим upstream account не считаются независимой capacity.


## Account discovery tests

- `/api/providers` возвращает несколько active connections одного provider;
- неактивные connections не участвуют в capacity;
- два подтверждённо независимых accounts создают два quota pools;
- два connections одного upstream account создают один quota pool;
- неизвестная независимость объединяется в shared pool;
- no-auth provider получает один virtual account;
- quota pool merge запускает новый global allocation;
- simple `connections.length × quota` нигде не используется.


## OmniRoute free/no-auth registry tests

- no-auth provider отсутствует в `/api/providers`, но найден через free registry;
- `/api/free-models` создаёт model definitions;
- одинаковый `poolKey` не суммируется по моделям;
- `poolKey` с account-specific quota получает account scope только после подтверждения;
- `keyless` не означает unlimited;
- `discontinued` endpoint исключён;
- provider без Arena score не удаляется из free registry;
- `/api/free-tier/summary` используется только для сверки;
- web-cookie provider с `hasFree` игнорируется automatic pipeline;
- video-only no-auth provider не попадает в LLM role combo;
- optional API key не создаёт вторую capacity без подтверждения.


## Web-cookie static candidate tests

- web-cookie provider не участвует в automatic model discovery;
- manual/static model проходит basic text probe;
- role с required tool calling исключает endpoint;
- role со strict JSON исключает endpoint;
- plain-text role допускает endpoint;
- unknown quota создаёт только opportunistic capacity;
- default policy делает endpoint fallback-only;
- manual OmniRoute configuration не удаляется orchestrator-ом.


## Artificial Analysis scoring v1 tests

- только пять разрешённых полей участвуют в score;
- output TPS: больше значение даёт больший normalized score;
- end-to-end: меньше значение даёт больший normalized score;
- P5/P95 clipping ограничивает влияние выбросов;
- missing metric перераспределяет веса и добавляет penalty;
- stale AA data добавляет uncertainty penalty;
- OmniRoute endpoint latency имеет приоритет над AA latency;
- отсутствие AA данных не исключает модель;
- разные роли используют разные веса;
- price, TTFT и прочие поля не влияют на scoring v1.


## Minimum context window tests

- provider-specific context overrides larger canonical context;
- effective context uses the minimum confirmed limit;
- 32K endpoint is excluded from a 64K-minimum role;
- 64K, 128K, 256K and 1M endpoint may share one role combo;
- larger context does not create a separate sub-combo;
- preferred context and similarity ratio are absent;
- max output token requirement is checked separately;
- unknown context is excluded unless manually overridden;
- context limit change invalidates scoring and allocation.


## Minimum quality gate tests

- роль принимает максимум одну gate-метрику;
- unsupported metric отклоняется;
- модель ниже intelligence minimum исключается;
- модель ниже agentic minimum исключается;
- модель без требуемой метрики считается unverifiable;
- unverifiable model исключается по default policy;
- weighted score рассчитывается только после gate;
- gate не ослабляется автоматически при малом combo;
- смена major index version требует recalibration;
- роль без gate продолжает использовать обычный weighted scoring.


## Artificial Analysis index migration tests

- new index version creates migration record;
- old thresholds remain active before approval;
- old metrics are preserved;
- same-percentile threshold suggestion is calculated;
- role capacity validation runs before proposal approval;
- major update cannot use patch fast path;
- low-drift patch can use compatible-patch path;
- high-drift patch requires full migration;
- rollout recalculates scores and combos;
- failed smoke test rolls back thresholds and combo snapshot;
- raw threshold from old index is never applied to new incompatible version.


## LLM-driven index migration tests

- healthiest endpoint with highest new intelligence index is selected;
- unavailable top model falls back to next highest;
- no available migration model keeps production unchanged;
- LLM receives distributions, role gates and capacity data;
- proposal must match JSON schema;
- invalid metric is rejected;
- threshold causing insufficient combo capacity is rejected;
- validation errors are returned for repair;
- maximum repair attempts are enforced;
- successful dry-run is required before rollout;
- old thresholds remain active until validated approval;
- percentile mapping is not enforced as the final decision.


## Instructor migration runtime tests

- Instructor wraps an OpenAI client configured with OmniRoute base URL;
- MigrationProposal is validated with Pydantic;
- invalid JSON triggers schema retry;
- unsupported metric triggers schema retry;
- schema retry count is limited;
- operational validation remains outside Instructor;
- operational errors trigger a separate migration-agent retry;
- credentials are not included in migration prompt;
- no agent framework or tool loop is required;
- failed structured generation leaves production unchanged.


## Agent and role demand forecasting tests

- two agents using one role have their demand summed;
- one agent using two roles contributes independently to both;
- cron schedule is projected exactly until quota reset;
- weekly burst is not flattened into an unsafe daily average;
- event-driven agent uses observed rate and p95;
- calls_per_agent_run expands request demand correctly;
- input and output token demand are calculated separately;
- all_agent_runs dependency contributes to a shared role;
- role_call dependency expands downstream role demand;
- cyclic role dependencies are rejected;
- maintenance workloads are included;
- observed profiles supersede bootstrap estimates only with sufficient samples;
- protected demand is used for guaranteed capacity;
- allocation fails when shared-role expansion causes oversubscription.


## Quota attribution tests

- missing OmniRoute quota_pool does not break demand accounting;
- official open-source quota definition creates attribution metadata;
- two accounts are not summed without confirmed independence;
- confirmed independent accounts add separate capacity;
- shared poolKey merges multiple endpoints into one capacity;
- unknown no-auth provider contributes zero guaranteed capacity;
- inferred independent group receives configured discount;
- account merge triggers allocation recalculation;
- account split requires confirmed evidence;
- Hermes combo usage can be forecast without exact quota attribution;
- actual OmniRoute endpoint usage maps to attribution group when available.


## Historical reserve and cold-start tests

- historical request forecast is multiplied by exactly 1.20;
- historical input tokens are multiplied by exactly 1.20;
- historical output tokens are multiplied by exactly 1.20;
- reserve is not applied twice after role aggregation;
- protected demand uses max of reserved history, p95, exact schedule and minimum;
- scheduled cold start uses exact Hermes run count;
- role bootstrap profile supplies calls and tokens per run;
- manual/event workload uses configured bootstrap frequency;
- completely unknown enabled role receives non-zero fallback demand;
- cold-start safety multiplier is applied to unknown estimates;
- history does not fully replace bootstrap before sample threshold;
- blended transition weights sum to one;
- exact future schedule remains authoritative after history becomes mature;
- insufficient confirmed quota produces cold_start_capacity_risk.


## Smart combo reviewer tests

- reviewer receives already-built priority combos;
- reviewer output accepts only add/remove/move;
- set_weight is rejected by schema;
- change_strategy is rejected by schema;
- add validates endpoint eligibility;
- remove revalidates combo size and protected demand;
- move preserves combo membership;
- invalid diff is rejected independently;
- valid sibling diffs are still applied;
- reviewer failure applies deterministic combo;
- no reviewer model applies deterministic combo;
- final combo always uses priority strategy;
- no endpoint weight is emitted;
- accepted and rejected diffs are audited.


## Dynamic role lifecycle tests

- a new declarative Hermes role is discovered;
- a new role gets cold-start demand before any history exists;
- a new role without a safe policy template becomes `needs_role_policy`;
- a missing role becomes `retiring`, not deleted;
- one failed discovery scan cannot delete a role;
- enabled cron reference blocks retirement completion;
- recent Hermes `state.db` usage blocks deletion;
- recent OmniRoute combo usage blocks deletion;
- a reappearing role cancels retirement and preserves history;
- protected role cannot be auto-deleted;
- explicit alias performs safe rename;
- unaliased old/new names are treated as retire + create;
- local dry-run performs no upstream request;
- orchestrator never calls `/api/combos/test`;
- retired combo deletion is idempotent.


## Daily Hermes inventory and environment tests

- full role/profile/routine inventory runs on the configured daily cron;
- unknown role triggers an immediate full inventory;
- unchanged inventory does not create duplicate consumers;
- new profile using an existing role updates the registry;
- removed routine is marked inactive;
- schedule change marks the forecast stale;
- calls_per_run change refreshes the Inspector forecast;
- inventory source hash makes reconciliation idempotent;
- filesystem mode validates required paths;
- command mode validates command configuration;
- HTTP mode validates URL configuration;
- missing `OMNIROUTE_URL` fails startup;
- missing `DATABASE_URL` fails startup;
- secrets are excluded from Inspector and reviewer payloads;
- startup does not call model endpoints.
