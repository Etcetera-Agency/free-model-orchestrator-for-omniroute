# Системный поток

## 1. Единица управления

Главная единица — не canonical model, а:

```text
provider account + provider model ID
```

Она называется `provider_endpoint`.

Пример:

```text
provider: kilo
account: kilo_oauth_denys
provider_model_id: anthropic/claude-sonnet-x
```

Одна canonical model может одновременно иметь несколько endpoint с разными:

- квотами;
- reset policy;
- latency;
- ошибками;
- доступностью;
- free-tier условиями.

## 2. Ежедневный полный цикл

### Шаг 1. Получить бесплатных кандидатов из models.dev

Metadata Sync загружает `catalog.json` и выбирает модели, для которых выполняется хотя бы одно условие:

```text
input cost = 0 AND output cost = 0
OR provider/model ID содержит token "free"
OR display name содержит отдельное слово "free"
```

Совпадение по названию является только кандидатом и не доказывает бесплатность.

В models.dev `cost` хранится на уровне **provider → model** (`providers[*].models[*].cost.{input,output}`), а не в плоском верхнеуровневом списке `models` (там цены нет). Поэтому zero-cost вычисляется по provider-keyed данным (`api.json` или секция `providers` из `catalog.json`): один и тот же model ID может быть платным у одного provider и бесплатным у другого. Отсутствие поля `cost` (так у части open-weights/local моделей) не равно `0` и само по себе кандидатом не делает.

### Шаг 2. Получить аккаунты и независимые quota pools

Account Discovery:

1. вызывает `/api/providers`;
2. получает активные connections;
3. вызывает `/api/rate-limits`;
4. сопоставляет connections с upstream accounts;
5. создаёт independent/shared quota pools;
6. добавляет virtual account для no-auth provider.

Количество connections не используется как прямой множитель quota.

### Шаг 3. Сопоставить с OmniRoute providers

Provider Scanner получает модели всех активных provider accounts.

Для каждого кандидата проверяется:

- есть ли такой provider model ID;
- есть ли alias/canonical match;
- у каких provider/account он доступен;
- появился ли новый endpoint;
- исчез ли старый endpoint.

Модели OmniRoute, которых нет среди кандидатов models.dev, не отбрасываются сразу. Они проверяются как provider-specific free quota candidates.

### Шаг 4. Проверить бесплатный доступ

Access Classifier сначала использует:

- `cost = 0` из models.dev как сильную подсказку;
- provider metadata;
- OmniRoute pricing/rate-limit data;
- сохранённые quota rules;
- результаты quota research.

Интернет-поиск нужен прежде всего для моделей с обычной платной ценой, доступных внутри provider-specific free quota, а также для неоднозначных `free` моделей.

### Шаг 5. Probe только изменений

Probe запускается только для:

- нового endpoint;
- endpoint с изменившейся моделью/capabilities;
- endpoint, который вернулся после удаления;
- endpoint с изменившимся правилом бесплатного доступа;
- endpoint, который давно не использовался и не имеет свежих runtime samples.

Все стабильные модели ежедневно заново не тестируются.

### Шаг 6. Обновить quality metadata

- Artificial Analysis scores;
- models.dev capabilities;
- последняя сохранённая OmniRoute latency/error telemetry;
- результат probe.

### Шаг 7. Пересчитать роли

Role Scorer пересчитывает только endpoint, у которых изменился `input_state_hash`.

### Шаг 8. Построить большие combo

Для каждой роли выбирается не 2–3 модели, а расширенный набор независимых endpoint.

Цель:

```text
много моделей в combo
+ разные provider groups
+ разные quota pools
+ разные model families
```

За счёт этого временное падение одной модели в течение дня обрабатывает OmniRoute без немедленного rebuild.

### Шаг 9. Применить минимальный diff

Combo меняется только если:

- появилась хорошая новая модель;
- модель исчезла;
- модель больше не бесплатна;
- quota rule закончился;
- endpoint хронически не работает;
- существенно изменился ranking.

## 3. Transaction boundaries

Каждый run имеет `sync_run.id`.

Изменение OmniRoute запрещено, если:

- PostgreSQL недоступен;
- нет snapshot текущего состояния;
- desired state не прошёл validation;
- access rule stale/conflicting;
- quota неизвестна;
- endpoint не прошёл probe.

## 4. Idempotency

Повтор одного run не должен:

- создавать дубли моделей;
- повторно добавлять тот же alias;
- изменять combo без diff;
- повторно выполнять дорогостоящий probe, если входные данные не изменились.

Idempotency keys:

```text
catalog_snapshot: provider_id + payload_hash
quota_source: source_url + content_hash
quota_rule: endpoint_id + rule_hash
probe: endpoint_id + probe_suite_version + model_revision
combo_apply: role_id + desired_state_hash
```
