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
- **auxiliary combos** snap **deterministically to the cheap auxiliary cell** (low
  tier) without a per-unit Inspector call — their function is narrow/mechanical, so
  the LLM verdict adds nothing. (A declared aux purpose may still bump a specific aux
  up later, but the default is the cheap cell.)

This keeps one uniform mechanism: no combo is hand-maintained, the Inspector is
spent only where "how smart" actually varies (the persona roles).
