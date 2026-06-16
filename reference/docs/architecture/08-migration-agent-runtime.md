
# Migration-agent runtime

## Decision

Use `Instructor` as a thin structured-output layer over the OpenAI-compatible OmniRoute endpoint.

## Architecture

```text
Free Model Orchestrator
  |
  | selects highest-intelligence available endpoint
  v
OpenAI Python SDK
  |
  v
OmniRoute /v1/chat/completions
  |
  v
Instructor
  |
  v
Pydantic MigrationProposal
  |
  v
Deterministic operational validator
```

## Non-goals

The migration-agent is not:

```text
a multi-agent system
a tool-using autonomous loop
a durable workflow engine
a memory system
```

## Minimal files

Suggested implementation:

```text
migration_agent/models.py
migration_agent/prompt.py
migration_agent/client.py
migration_agent/service.py
```

### models.py

Contains only Pydantic schemas.

### prompt.py

Contains system prompt and migration input formatter.

### client.py

Creates:

```text
OpenAI client
Instructor wrapper
```

### service.py

Runs one proposal call and exposes:

```python
generate_migration_proposal(input_data, selected_model)
```

Operational validation remains outside this package.

## Retry policy

```text
Instructor schema retries: 3
Orchestrator operational repair retries: 3
```

These retry counters are separate.

## Security

Migration-agent receives only:

```text
model metrics
role definitions
quota pool summaries
health summaries
current thresholds
```

It must not receive:

```text
provider API keys
OAuth tokens
cookies
raw credentials
```

## Output trust boundary

The LLM output is untrusted until:

```text
Pydantic validation passed
operational validation passed
dry-run passed
approval passed
```
