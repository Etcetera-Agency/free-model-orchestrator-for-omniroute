# Change: Configured auto-router fallback tail on every combo

## Why

Provider "auto-router" / free-router meta-models — `openrouter/free` (Free Models
Router), `mimocode/mimo-auto`, `kilo-auto/free` — pick the underlying model
dynamically per request. There is therefore no stable underlying model whose
Artificial Analysis `intelligence_index` / `coding_index` / `agentic_index` could
be read, so an AA quality band for them is meaningless. They cannot be ranked
against scored endpoints; they only make sense as a last-resort fallback.

Today nothing recognizes them as a class:

- `aa_subscore` ([src/fmo/scoring.py:42](../../../src/fmo/scoring.py)) just sees
  all three quality indices missing, returns `unknown=True, value=None`, and
  applies an uncertainty penalty.
- `score_endpoint` then treats the missing `benchmark_fit` as `0` and subtracts
  the uncertainty, so the router lands at a **near-zero or negative score**.
- `build_priority_combo` ([src/fmo/allocation.py:54](../../../src/fmo/allocation.py))
  orders by score **ascending**, where position 0 is the primary. A near-zero
  score therefore sinks the router to **position 0 — it becomes the primary** —
  the exact opposite of the intended last-resort fallback, and it consumes a
  `per_pool_cap` slot a real scored endpoint should hold.

These routers are also named inconsistently (`/free`, `-auto`, `/auto`), and
their catalog `cost` is an unreliable `0/0` default (`openrouter/auto` and
`orcarouter/auto` are actually paid). A naming pattern is therefore not a safe
selector. Instead this slice uses a small **curated, ordered config list** of
known free routers, validated at runtime, appended as the fallback tail of every
combo.

## What Changes

- Add a config setting `auto_router_tail`: an ordered list of router entries, each
  with an `id` and its declared `input` modalities. Default:
  `[{id="mimocode/mimo-auto", input=["text"]},
  {id="kilo-auto/free", input=["text"]},
  {id="openrouter/free", input=["text","image"]}]`. Order is the tail priority —
  earlier entries sit closer to the scored endpoints. Modalities are declared in
  config because the catalog cost and capability defaults are not trusted; the
  context window is NOT declared here — routers reuse the existing
  `effective_context_window` computation and context-window hard filter like any
  endpoint (OmniRoute `context_length` is a reliable source, unlike `cost`).
- An endpoint is treated as a router only if its `id` matches a configured entry
  exactly (provider-flexible canonical match). Membership is NOT inferred from a
  naming pattern, and parent/child catalog links are NOT collapsed:
  `mimocode/mimo-auto` is an independent entry matched on its own id and is not
  treated as an alias of its parent `mcode/mimo-auto`.
- Routers SHALL NOT be AA-scored: skip `aa_subscore`/`benchmark_fit` and emit no
  uncertainty penalty for missing quality indices.
- Routers SHALL be exempt from the role quality band / quality-gate: a router has
  no stable underlying model, so a band is inapplicable; the existing
  `unverifiable`-gate exclusion MUST NOT drop them. They are eligible only as the
  fallback tail, never as a band-ordered scored member.
- During combo composition, after the scored head is built, the configured
  routers are appended as a tail in config order, but only those that for this
  role: pass the access filter as free (the catalog `cost` is not trusted), cover
  the role's required input modalities per the router's **config-declared**
  `input`, meet the role's context-window minimum via the existing
  `effective_context_window` hard filter, and pass probe/quota/breaker. A router
  that fails any of these is skipped for that role (e.g. a `text`-only router is
  skipped for a role that requires `image` input; a router whose effective context
  is below the role minimum is skipped by the existing context filter).
- Routers do not consume the scored-slot `per_pool_cap`; the tail is bounded by
  its own `auto_router_tail` length.
- A combo MAY consist only of routers when no scored endpoint is eligible; the
  no-paid-fallback invariant is preserved (only routers that pass the free access
  filter qualify).

## Impact

- Affected specs: `role-scorer`, `allocator`, `quality-gate`.
- Affected code: `src/fmo/config.py` (`auto_router_tail` setting + membership
  helper), `src/fmo/scoring.py` (skip AA branch for tail members),
  `src/fmo/quality.py` (band exemption), `src/fmo/allocation.py`
  (`build_priority_combo` appends the filtered config tail),
  `src/fmo/composition_stages.py` (carry router membership into the score map),
  `tests/`.
- No new network calls, no paid fallback, ordering stays deterministic.
