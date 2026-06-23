# Design: tiering the default combo grid

## Evidence (free-model AA distribution)

From the captured fixture `artificial_analysis_language_models_free.json`
(511 free models, 503 with an intelligence index):

| axis         | n   | max  | p75  | p90  | ≥40 |
|--------------|-----|------|------|------|-----|
| intelligence | 503 | 59.9 | 26.1 | 36.5 | 33  |
| coding       | 416 | 74.9 | 34.0 | 43.0 | 56  |
| agentic      | 384 | 80.6 | 48.8 | 60.9 | 133 |

Intelligence median is 14.1; the distribution is a long tail clustered low
(190 models in 0–9). Top intelligence models: Claude Fable 5 (59.9), Opus 4.8
(55.7), GPT-5.5 xhigh (54.8).

## Decisions driven by the data

1. **No `frontier` tier.** Free-model ceilings are ~60/75/81; nothing approaches
   90–100. A fourth tier would be empty. MVP fixes **3 tiers** (low/medium/high).

2. **Tier boundaries are per-axis, not a shared absolute cut.** The axes differ in
   range by 2–3×, so a fixed `high = ≥40` selects ~33 models on intelligence (true
   elite) but ~133 on agentic (a third of the pool — meaningless as "high"). Tier
   cut points SHALL be derived from each axis's own distribution over the
   confirmed-free pool (e.g. tertiles), and the `(axis, tier) → anchor` value is the
   median of that bucket.

3. **Fixed tier count, data-driven boundaries** is the MVP. Full density-based
   clustering (variable tier count per axis) remains a follow-up; per-axis tertiles
   already capture the bulk of the benefit cheaply.

## Capacity on the *registered* pool (not the whole free list)

The tier boundaries above come from the full AA free list (503 models). The pool
that actually matters is what OmniRoute has **registered** —
`omniroute_v1_models.json` `body.data`: 463 entries = 450 provider models + 13
combos. Matching the 450 provider models to AA (312 matched, 138 unscored):

| intelligence tier | registered endpoints |
|-------------------|----------------------|
| low (<20)         | 153 |
| medium (20–40)    | 121 |
| high (≥40)        | 38 (13 distinct models) |

- **High-tier capacity is real but thin and concentrated**: 38 endpoints across
  only 13 underlying models (Gemini 3.5 Flash, MiniMax-M3, Gemini 3.1 Pro, Kimi
  K2.6, GLM-5.1/5.2, DeepSeek V4 Pro…). Many are one model via several providers, so
  they share per-provider quota — effective high-tier capacity is below 38.
- **The pool is heavily multi-modal.** Of 450 provider models, ~102 are non-text
  endpoints (embeddings, ASR/TTS like whisper/voxtral/parakeet, image/video gen like
  veo/lyria/flux, OCR, moderation, rerank). These legitimately have no AA index and
  are **out of intelligence tiering** — they are matched to roles by capability, a
  separate axis from "how smart". Tiering operates on the ~348 text/chat models only.
- Genuinely AA-unscored *chat* models are a small niche tail (low tens — old/domain
  models like palmyra-med, llama2-70b), handled by the existing router/uncertainty
  path (`aa_subscore`/`score_endpoint` `is_router`). (An earlier 138/30% figure was a
  fuzzy-match artifact: it conflated non-text endpoints and matcher misses of scored
  models such as mistral-medium/devstral/gemma3 — not true unscored coverage.)
- The band's existing `degraded` flag already signals when a band lacks capacity for
  `protected_requests`; high-intelligence roles are the likely degraded case and
  should be monitored, not silently widened past the floor.

## The grid is not greenfield

`omniroute_v1_models.json` already registers 13 `fmo-*` combos: main role combos
(`fmo-chat-combo`, `fmo-research-combo`, `fmo-coding-combo`) and auxiliary/task
combos (`fmo-title-generation`, `fmo-vision`, `fmo-compression`, `fmo-approval`,
`fmo-skills`, `fmo-mcp`, `fmo-triage-specifier`, `fmo-kanban-decomposer`,
`fmo-profile-describer`, `fmo-curator`). The default `axis × tier` grid SHALL
reconcile with these existing combos rather than mint a parallel set.

**All combos snap to the grid — including the auxiliaries** (decision: don't
hand-maintain them, don't overthink). The grid covers every combo:
- **main roles** (`fmo-chat`/`research`/`coding`) get their `(axis, tier)` cell from
  the intelligence Inspector's persona-derived anchor;
- **auxiliary combos** snap **without a per-unit Inspector call** — their cognitive
  load is low so the LLM verdict adds nothing.

**But "cheap" is not one cell — capability gates first.** The auxiliaries differ by
tooling, so they cannot share a single cheap cell: `fmo-vision` needs vision,
`fmo-mcp`/`fmo-skills` need tool-calling, `fmo-approval`/`fmo-triage-specifier` need
structured output, `fmo-compression`/`fmo-title-generation` are plain text. Observed
capability supply in the registered pool: `tool_calling` 450, `reasoning` 463,
`thinking` 76, **`vision` only 52** (scarce). So there is a **dedicated auxiliary
combo per capability**, each built from the cheapest models satisfying that
capability — i.e. `(lowest tier) ∩ (capability filter)`, a ranked member list like
any other cell, not a flat cheap cell and not a single model. Concretely the aux
family is `aux-text`, `aux-tools`, `aux-vision`, `aux-structured`, and each existing
aux role points at the combo matching its profile.

Capability is a hard `issubset` filter (already enforced in `scoring.py`
`required_capabilities`) applied **before** tier on every cell — vision-aux is the
capacity-thin case (52 endpoints) and should be monitored like the high-intelligence
cell. This keeps one uniform mechanism: no combo is hand-maintained, the Inspector is
spent only where "how smart" actually varies (the persona roles).

## The grid is keyed by the full requirement profile, not just axis × tier

A grid cell must be a **real, populated combo** that satisfies a role's *whole*
profile — so capability and context window are **dimensions of the cell, not
post-filters on a generic cell**. A role needing vision + 1M context + high
intelligence requires a combo that actually exists for that profile; filtering a
generic high-intelligence cell down could leave it empty. The cell key is the tuple:

```
(axis, tier, required_capabilities, context_class)
```

- `axis`, `tier` — from the intelligence Inspector (persona-derived anchor);
- `required_capabilities` — hard `issubset` (vision / tool_calling / structured),
  already enforced in `scoring.py`;
- `context_class` — bucket of `minimum_context_window`, gated on the trustworthy
  `effective_context_window` (probed-over-advertised) via the existing
  `_context_window_eligibility` / `_router_tail_eligible`.

**Avoiding the cartesian explosion.** The full product (3 axes × 3 tiers × ~4
capability sets × ~3 context classes ≈ 100+) is NOT pre-built. The grid is
**demand-driven**: enumerate the *distinct profile tuples that real Hermes roles +
aux functions actually exhibit*, and build one reusable combo per occurring tuple.
Most roles collapse onto a handful of tuples (reuse); a tuple seen once mints a
unique combo. So the grid size tracks the real role population, not the theoretical
space.

`context_class` source: `minimum_context_window` per role =
`max(`static `requirements.minimum_context_window`,
demand Inspector `average_input_tokens × headroom)`. The demand forecast already
estimates input tokens, so a document-ingesting role pulls a big-context tuple
without a separate signal.

Registered supply shaping the thin tuples: context 128–200k is the bulk (282), but
**1M+ is only 58** and **vision only 52** — tuples combining high-intelligence +
1M + vision are the capacity-thin corners; expect the band `degraded` flag there.

## Lifecycle: bootstrap once, then evolve

The grid is **set up once** (the fresh-deploy bootstrap). Bootstrap is minimal:
each default combo is created with a **single seed model** — the seed sets the
cell's initial anchor (its profile-tuple representative). Bootstrap does NOT
pre-fill ~8-member lists. This reuses the existing `_seed_quality_bands`
(anchor from one seed endpoint) + `quality_band_for_demand` (widen by demand).

It is never re-bootstrapped wholesale. After setup it evolves only two ways:

1. **Agent-driven rebalance** of existing cells — the agents that route to a combo
   drive it: their forecast demand widens the band around the seed anchor to meet
   capacity, and members re-rank by score. So the combo grows from one seed to a
   full member list *because of the agents on it*, not at bootstrap.
2. **Lazy addition of unique per-agent combos** — when a new agent/profile appears
   whose profile tuple `(axis, tier, capability, context)` no existing cell covers, a
   unique combo is minted (again seeded with one model, then agent-rebalanced).

So steady state = agent-driven rebalance + incremental unique combos. Bootstrap is a
one-time single-seed-per-cell, not a recurring job and not a pre-filled grid.

## The grid cells are living combos — they rebalance

Grid cells are not frozen at bootstrap. They are ordinary FMO combos and ride the
existing rebalance machinery:

- **Reorder** (`allocation.py` `build_priority_combo`/reorder): members are
  priority-ranked by score (quota_headroom, health, stability) and re-sorted, but
  only when the improvement clears a threshold (hysteresis — avoids churn).
- **Recalibration** (`quota_recalibration.py`, scheduler `tick_recalibration` cron):
  tokens-per-request and capacity refresh → the band may widen/narrow → cell
  membership shifts.
- **Reactive triggers** (provider-added, urgent-paid-charge) plus the full daily run.
- **Drift-guarded apply** (`apply.py`): live OmniRoute combo set is source of truth;
  apply refuses (`combo_drift_detected → unsafe_to_apply`) rather than clobber a
  combo that moved underneath.

**Separation that makes this composable:** the intelligence grid owns *targets* —
the profile tuple and the **anchor** (the persona-derived quality centre). The
existing rebalance/recalibration owns the *live membership and ordering* around that
target over time. Therefore:

- The intelligence **anchor MUST be stable across rebalances** — it is recomputed
  only on a persona/description-hash change, NOT on every quota recalibration.
  Otherwise the band centre would move under the rebalancer and cause churn.
- A rebalance may temporarily drop a thin-corner cell (high-intel / 1M / vision)
  below its anchor as quota depletes; the anchor stays fixed and the band's
  `degraded` flag signals the shortfall — the cell is not silently re-anchored down.
- Bootstrap sets only the initial membership; from then on reorder + recalibration
  keep each cell healthy around its stable anchor.
