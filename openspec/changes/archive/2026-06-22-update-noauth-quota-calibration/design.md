# Design: No-auth quota calibration

## Context

OmniRoute no-auth providers are not all independent quota surfaces. Some are
provider aliases over the same upstream access as an authenticated provider. The
known current case is:

- `opencode` no-auth provider page:
  `https://omniroute.etc2nd.etcetera.agency/dashboard/providers/opencode`
- `opencode-zen` authenticated sibling page:
  `https://omniroute.etc2nd.etcetera.agency/dashboard/providers/opencode-zen`

For that class, FMO should not invent a separate no-auth budget. It should bind
the no-auth provider to the authenticated sibling's model set and quota rule.

Some no-auth providers have no reliable quota source. Search or registry data
can identify that the provider exists, but not the limit, reset, or hard-stop
semantics. Those providers need an operator calibration loop before FMO treats
them as usable quota.

## Decision

No-auth provider quota handling has two explicit paths:

- Alias path: a documented mapping says a no-auth provider shares quota and
  models with an authenticated sibling. FMO uses the sibling quota/model source
  and stores the no-auth provider as shared capacity, not independent capacity.
- Calibration path: if no quota source is known, FMO marks the endpoint
  calibration-required. Operator puts it first in a combo, sends controlled
  traffic, checks OmniRoute token usage, then records the observed quota before
  capacity becomes usable.

## Pseudocode

```python
def resolve_noauth_quota(provider_id, model_id):
    alias = noauth_aliases.get(provider_id)
    if alias:
        sibling_rule = quota_rules.lookup(alias.auth_provider_id, model_id)
        sibling_models = catalogs.lookup(alias.auth_provider_id)
        return SharedQuotaRule(
            provider_id=provider_id,
            shared_with=alias.auth_provider_id,
            models=sibling_models,
            limit=sibling_rule.limit,
            reset=sibling_rule.reset,
            hard_stop=sibling_rule.hard_stop,
        )

    known_rule = quota_rules.lookup(provider_id, model_id)
    if known_rule and known_rule.has_safe_bound:
        return known_rule

    return CalibrationRequired(
        provider_id=provider_id,
        model_id=model_id,
        action="place_first_in_combo_and_observe_omniroute_token_usage",
    )
```

```python
def promote_calibrated_noauth(provider_id, observed_usage):
    if not observed_usage.has_limit or not observed_usage.has_reset:
        keep_status(provider_id, "calibration_required")
        return

    quota_rules.upsert(
        provider_id=provider_id,
        limit=observed_usage.limit,
        reset=observed_usage.reset,
        hard_stop=observed_usage.hard_stop,
        source="operator_observed_omniroute_usage",
    )
```

## Risks

- Operator traffic can spend unknown quota if the combo is not controlled.
  Mitigation: calibration placement is first-member only for controlled
  observation and does not promote quota until token usage evidence is recorded.
- Alias mapping can drift if OmniRoute changes provider topology. Mitigation:
  mapping is explicit and reviewed against provider pages before activation.
