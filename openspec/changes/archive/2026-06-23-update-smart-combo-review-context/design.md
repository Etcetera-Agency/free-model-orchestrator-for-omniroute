# Design: smart-combo-reviewer context bundle

## Context

Quota and Hermes inspectors use explicit prompt files and named context values.
They are still deterministic around the edges: Python assembles/redacts input,
Instructor validates output, and downstream code decides what to trust.

`smart-combo-reviewer` should follow that same architecture. The reviewer can
only propose useful diffs if it sees the facts the deterministic planner used.

## Goals

- Give reviewer enough context to explain or challenge the deterministic combo.
- Keep reviewer advisory: no LLM output changes the applied combo in this slice.
- Keep input bounded, redacted, deterministic, and testable.
- Use one shared Instructor runtime and the external prompt file.
- Consume the structured member identity produced by
  `update-combo-member-identity` so provider/model/account and canonical-family
  rebalance suggestions are validateable.

## Non-Goals

- No automatic application of reviewer diffs.
- No repair loop.
- No extra live OmniRoute requests from the reviewer path.
- No new quota or scoring authority owned by the LLM.
- No implementation before `update-combo-member-identity` lands.

## Payload Shape

The reviewer context SHALL be a JSON-serializable, stable-sorted all-cells
`review_brief`, not a one-role payload:

```json
{
  "run": {"run_id": "uuid", "schema_version": 1},
  "cells": [
    {
      "combo_id": "fmo-grid-int-high",
      "cell_profile": {
        "axis": "intelligence_index",
        "tier": "high",
        "anchor": 80,
        "required_capabilities": ["text"],
        "context_class": "default",
        "auxiliary": false,
        "reusable": true
      },
      "snapped_consumers": [
        {
          "role_id": "research",
          "consumer_type": "agent_profile",
          "protected_requests": 25,
          "average_input_tokens": 2000,
          "average_output_tokens": 1000,
          "criticality": 1,
          "purpose_summary": "grounded research and synthesis",
          "inspector_confidence": "high"
        }
      ],
      "current_members": [],
      "target_members": [],
      "member_groups": [],
      "candidate_alternatives": [],
      "constraint_report": {}
    }
  ],
  "scarce_pools": [],
  "candidate_registry": [],
  "deterministic_rules": {},
  "validation_report": {}
}
```

## Pseudocode

```python
def _review_diff(dependencies, diff, plan):
    if smart_review_disabled:
        return run_combo_review(..., trigger=False)
    if dependencies.llm_runtime is None:
        return ComboReviewResult(status="failed", ...)

    brief = build_combo_review_brief(
        transaction=transaction,
        plans=plans,
        current_combos=current,
        run_id=context.run_id,
    )

    return run_combo_review(
        dependencies.llm_runtime,
        review_context={"review_brief": brief},
        trigger=True,
    )
```

```python
def build_combo_review_brief(...):
    cells = summarize_cells_with_snapped_consumers(plans, current_combos)
    scarce_pools = summarize_global_pool_pressure(cells)
    candidate_registry = summarize_referenced_candidates(cells, max_candidates_per_cell=24)
    validation = deterministic_validation_report(cells, scarce_pools)

    return redact_and_stable_sort({
        "run": {"run_id": str(run_id), "schema_version": 1},
        "cells": cells,
        "scarce_pools": scarce_pools,
        "candidate_registry": candidate_registry,
        "deterministic_rules": deterministic_rules_summary(),
        "validation_report": validation,
    })
```

## Decisions

- The context builder lives in deterministic Python, not in prompt text.
- The reviewer sees all cells as a compressed summary. Each cell includes snapped
  consumers and pressure; detailed endpoint rows are bounded to selected members
  and nearby alternatives.
- Prompt overflow is handled by reducing candidate detail/alternative count
  before assembly. Required top-level sections are never omitted.
- Reviewer result persistence shape stays unchanged:
  `status`, `valid_diffs`, `rejected`.

## Risks / Mitigations

- Risk: prompt grows too large.
  Mitigation: deterministic summarization and `max_prompt_chars` tests.
- Risk: secrets from provider/account config leak into prompt.
  Mitigation: reuse shared runtime redaction and add context-level tests for
  secret-like keys.
- Risk: reviewer appears authoritative.
  Mitigation: keep production tests proving applied diff is byte-identical with
  reviewer enabled, disabled, or failed.
