# Combo grid bootstrap — combos to create on the server

Input list for a **separate task**: create the default combo grid on the live
OmniRoute. Design rationale lives in the `add-intelligence-inspector` openspec
change (`proposal.md` / `design.md`) and the deploy runbook
(`ORACLE_FRESH_SERVER_DEPLOY.md` §7a). This file is just the concrete list.

## Rules (read before creating)

- **One-time bootstrap, minimal.** Each combo is created with a **single seed
  model** that sets the cell's anchor. Do NOT pre-fill member lists — the
  agent-driven rebalance grows each combo later (`quality_band_for_demand`).
- **Seeds below are CANDIDATES from fixture data and must be regenerated with the
  FMO matcher** (`src/fmo/matcher.py` + `aa_index_runtime`) against live AA +
  registered models before creation. They came from fuzzy name matching, which
  mislabels models; do not paste them into a live combo unverified.
- **Additive.** Leave the 13 existing `fmo-*` combos in place; create these
  alongside, then migrate roles. Back up `GET /api/combos` to `bak-wf/` first.
- **Create payload shape** (per `/api/combos`): `{ name, models: [{ kind:"model",
  model:"<provider/id>", providerId, weight:0 }], strategy:"priority" }`.
- Hard filters that define each cell (applied by the matcher when picking the
  seed and later members): `required_capabilities` (`issubset`) and context window
  (`effective_context_window ≥ minimum`). Context class here is the **default**
  (≥128k); large-context variants are minted on demand, not at bootstrap.

## A. Axis × tier grid (9 combos)

Tiers = per-axis tertiles of the registered text pool; anchor = median of the band.
Reference cuts (2026-06-22 fixture, regenerate live): int 10.0/29.4, cod 15.5/37.4,
agt 18.8/53.2.

| combo name          | axis               | tier   | anchor≈ | seed candidate (verify)                       |
|---------------------|--------------------|--------|---------|-----------------------------------------------|
| `fmo-grid-int-low`  | intelligence_index | low    | 7.3     | `nvidia/mistralai/mistral-large-2-instruct`   |
| `fmo-grid-int-med`  | intelligence_index | medium | 20.1    | `antigravity/gemini-2.5-flash`                |
| `fmo-grid-int-high` | intelligence_index | high   | 38.1    | `nvidia/minimaxai/minimax-m2.7`               |
| `fmo-grid-cod-low`  | coding_index       | low    | 10.0    | `mistral/ministral-8b-2512`                   |
| `fmo-grid-cod-med`  | coding_index       | medium | 25.2    | `ollamacloud/qwen3-coder:480b`                |
| `fmo-grid-cod-high` | coding_index       | high   | 42.9    | `oc/qwen3.6-plus-free`                        |
| `fmo-grid-agt-low`  | agentic_index      | low    | 8.5     | `nvidia/nvidia/nemotron-3-nano-30b-a3b`       |
| `fmo-grid-agt-med`  | agentic_index      | medium | 30.1    | `antigravity/gpt-oss-120b-medium`             |
| `fmo-grid-agt-high` | agentic_index      | high   | 61.7    | `oc/qwen3.6-plus-free`                        |

## B. Auxiliary family (4 combos)

Cheapest model satisfying the required capability (no Inspector call). The existing
aux combos point at the matching family member.

| combo name           | required capability | seed candidate (verify)              | feeds (existing aux combos)                                   |
|----------------------|---------------------|--------------------------------------|--------------------------------------------------------------|
| `fmo-grid-aux-text`  | none (plain text)   | `nvidia/google/gemma-3n-e2b-it`      | `fmo-title-generation`, `fmo-compression`, `fmo-curator`, `fmo-profile-describer` |
| `fmo-grid-aux-tools` | `tool_calling`      | `nvidia/google/gemma-3n-e2b-it`      | `fmo-mcp`, `fmo-skills`, `fmo-triage-specifier`, `fmo-kanban-decomposer` |
| `fmo-grid-aux-struct`| structured output   | `nvidia/google/gemma-3n-e2b-it`      | `fmo-approval`                                                |
| `fmo-grid-aux-vision`| `vision`            | `antigravity/gemini-2.5-flash-lite`  | `fmo-vision`                                                  |

Note: `aux-text`/`aux-tools`/`aux-struct` seed to the same cheapest model only
because it happens to carry `tool_calling`; their capability filters diverge the
combos during rebalance.

## C. Main role combos

`fmo-chat-combo`, `fmo-research-combo`, `fmo-coding-combo` already exist. Reconcile
them into the grid (snap to the cell matching each role's Inspector-resolved
profile) rather than creating parallels.

## Capacity warnings (thin corners — expect band `degraded`)

- high-intelligence registered endpoints ≈38 (≈13 models, quota-shared per provider)
- 1M+ context ≈58 endpoints; `aux-vision` draws from `vision` ≈52 endpoints

## Bootstrap step (server, internal API; back up first)

```bash
mkdir -p /opt/apps/omniroute/bak-wf
KEY=<temporary manage-scope key>   # delete after
curl -fsS -H "Authorization: Bearer $KEY" http://127.0.0.1:20129/api/combos \
  > /opt/apps/omniroute/bak-wf/combos-$(date +%Y%m%d-%H%M%S).json
# then POST /api/combos for each combo above with its matcher-verified seed.
```
