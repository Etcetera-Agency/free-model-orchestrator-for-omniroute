# Grill: smart-combo-reviewer context
Date: 2026-06-23

## Intent
Make `smart-combo-reviewer` useful by letting it evaluate default combo grid
cells against the roles/consumers snapped to those cells, then propose safe
membership/order improvements that deterministic code can validate and apply.

## Constraints
- Reviewer suggestions may apply only after deterministic validation.
- Reviewer must account for role demand, consumer mix, and cell pressure.
- Reviewer must understand quota pools, provider/account identity, canonical
  model identity, and model family concentration.
- Default combo grid owns stable profile targets and anchors; rebalance owns
  live membership/order.
- Code must first support structured combo member identity before LLM patches
  can safely target provider/model/account variants.

## Key decisions
- Decision: Create a code slice before the LLM slice. Reason: current apply path
  writes plain member strings and cannot express account-pinned
  provider/model/account choices. Alternative considered: give richer context to
  LLM first; rejected because proposed patches could not be rendered safely.
- Decision: Reuse existing canonical model grouping from model matcher/profile
  normalization. Reason: the repo already groups raw provider models by canonical
  slug for profile normalization; allocation/rebalance just does not use it yet.
  Alternative considered: invent a new grouping model; rejected as duplicate.
- Decision: LLM review should operate over all grid cells summary. Reason:
  rebalance decisions can shift capacity and members across cells; a single-cell
  prompt misses shared quota and model-family pressure.

## Surfaced assumptions
- “Same underlying model” grouping exists in profile normalization and canonical
  model metadata, but not in combo allocation/rebalance.
- OmniRoute combo steps support `connectionId`; FMO currently does not render
  those structured steps.
- The reviewer should suggest improvements for semantic fit, overkill/scarcity,
  concentration, and thin-corner handling; divergent consumer mix should lead to
  complementing/splitting suggestions, not blind role-level optimization.

## Out of scope
- Direct LLM changes to anchor, axis, tier, or role definitions.
- Applying split-cell/topology changes automatically in the first LLM slice.
- Pushing or committing changes.
