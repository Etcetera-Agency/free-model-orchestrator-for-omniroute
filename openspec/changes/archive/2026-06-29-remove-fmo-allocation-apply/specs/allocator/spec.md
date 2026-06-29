# allocator Specification

## REMOVED Requirements

### Requirement: Global allocation before combos
**Reason**: The one-generation global solve moves to OmniRoute (`add-fmo-pools-solve-tail`), which owns live quota and the request path.
**Migration**: OmniRoute builds the head inventory and reserves capacity during materialization; FMO publishes demand + constraints only.

### Requirement: Hard constraints and heavy-role separation
**Reason**: Capability/context/free gates and pool separation are enforced by OmniRoute's fill ladder and reservation.
**Migration**: FMO declares `capabilities`, `min_context_tokens`, and `free_only`; OmniRoute applies them as hard gates.

### Requirement: Oversubscription gate
**Reason**: Capacity-vs-demand comparison requires request-path ground truth (live quota, `tokens_per_request`), owned by OmniRoute.
**Migration**: OmniRoute's request-equivalents comparator handles oversubscription.

### Requirement: One priority combo per role, no weights
**Reason**: FMO no longer writes combo members; OmniRoute materializes combos as `strategy=priority`.
**Migration**: OmniRoute orders head + tail and writes the priority combo.

### Requirement: Degraded modes, no paid fallback
**Reason**: Degradation/fallback is decided at materialization and runtime by OmniRoute (config-driven tail + free gate).
**Migration**: OmniRoute's free gate and capability-filtered tail enforce no-paid-fallback.

### Requirement: Stability
**Reason**: Incumbency stability and account stickiness move into the OmniRoute global solve.
**Migration**: OmniRoute loads the previous generation as an incumbency prior and applies stability among eligible candidates.
