# Design — auxiliary slots as consumers

## Auxiliary slot shape (verified upstream v2026.6.19)

`configuring-models.md` lists the auxiliary task slots; `cli-config.yaml.example`
shows the per-slot shape:

```yaml
auxiliary:
  vision:        {provider: omniroute, model: fmo-gemini-flash}  # explicit override
  web_extract:   {provider: auto,      model: ''}                # auto → main combo
  compression:   {provider: auto,      model: ''}
  # task keys seen upstream: vision, web_extract, compression, title_generation,
  # approval, mcp, skills, triage_specifier, kanban_decomposer, profile_describer,
  # curator, tts_audio_tags, session_search
```

Rule: a slot is a separate consumer **iff** it routes somewhere other than the
main combo. `provider: auto` or empty `model` ⇒ it uses the main model ⇒ not a
separate consumer (`configuring-models.md`: "auto … use the main model for that
task").

## Enumeration (pseudocode)

```python
def parse_profile_consumers(profile, *, demand_by_combo) -> list[Consumer]:
    out = []
    main = profile.main_combo                       # may be None (unconfigured)
    is_service = profile.gateway_running

    if main is not None:
        out.append(Consumer(
            role_id=_combo_role(main),
            consumer_type="service" if is_service else "agent_profile",
            consumer=profile.name,
            cadence="continuous" if is_service else "interactive",
            calls_per_run=demand_by_combo.get(_combo_role(main), BOOTSTRAP_CALLS_PER_RUN),
        ))

    for slot, cfg in (profile.auxiliary or {}).items():
        combo = _resolved_aux_combo(cfg, main)      # None when auto/empty
        if combo is None:
            continue                                # falls back to main — already counted
        out.append(Consumer(
            role_id=_combo_role(combo),
            consumer_type="auxiliary",
            consumer=f"{profile.name}:{slot}",      # carries slot for capability later
            cadence="auxiliary",
            calls_per_run=demand_by_combo.get(_combo_role(combo), BOOTSTRAP_CALLS_PER_RUN),
        ))
    return out


def _resolved_aux_combo(cfg, main_combo) -> str | None:
    if not isinstance(cfg, dict):
        return None
    if (cfg.get("provider") or "").lower() == "auto":
        return None                                 # auto = use main
    model = cfg.get("model")
    return model or None                            # empty model = use main
```

`parse_gateway_services` gets the same auxiliary treatment: a top-level
`auxiliary` block and any per-platform `auxiliary` override emit `auxiliary`
consumers keyed `f"gateway:{platform}:{slot}"`.

## Demand aggregation

`forecast.aggregate_demand` already sums `calls_per_run` per role across
consumers, so two slots pointing at the same combo sum naturally — the only
change is that auxiliary consumers now exist to be summed. No new forecast math;
a test must prove the sum.

```
default.auxiliary.vision  → fmo-gemini-flash  (demand d1)
coder.auxiliary.vision    → fmo-gemini-flash  (demand d2)
=> role fmo-gemini-flash protected demand reflects d1 + d2
```

## Out of scope

Capability-per-slot mapping (vision → vision-capable, etc.) and the combo's
quality band belong to `add-forecast-driven-quality-band`. Here the slot name is
only recorded on the consumer so the later slice can derive capability.
