# quota-manager Specification

## REMOVED Requirements

### Requirement: Effective remaining counter
**Reason**: Live remaining is request-path ground truth owned by OmniRoute.
**Migration**: OmniRoute reads remaining via `getUsageForProvider` / quota snapshots.

### Requirement: Hard-stop gating
**Reason**: Hard-stop/exhaustion gating happens at OmniRoute runtime (cooldown/lockout).
**Migration**: OmniRoute cooldown + model lockout enforce hard stops.

### Requirement: Reservation only for own probes
**Reason**: FMO no longer probes; capacity reservation moves to the OmniRoute solve.
**Migration**: OmniRoute reserves capacity during the global solve.

### Requirement: Reset handling
**Reason**: Reset is read from live quota / reset-aware path in OmniRoute.
**Migration**: OmniRoute reset-aware scoring handles reset windows.

### Requirement: Historical reserve guard
**Reason**: Demand-side reserve stays in FMO forecast; quota-side reserve moves to OmniRoute.
**Migration**: `forecast.apply_historical_reserve` stays; quota reserve is OmniRoute's.

### Requirement: Live quota source fetch
**Reason**: Live quota fetch is OmniRoute's.
**Migration**: `getUsageForProvider` and provider fetchers in OmniRoute.

### Requirement: Quota unit normalization
**Reason**: The request-equivalents conversion algebra moves to OmniRoute.
**Migration**: OmniRoute owns `to_requests_per_day` / `binding_capacity` equivalents.

### Requirement: Capacity bound across axes in request-equivalents per day
**Reason**: The tightest-axis comparator moves to OmniRoute.
**Migration**: OmniRoute `capacity.ts` computes the request-equivalents bound.

### Requirement: Weekly recalibration of the global tokens-per-request factor
**Reason**: `tokens_per_request` learning needs `observed_tokens/observed_requests` from the request path.
**Migration**: OmniRoute owns the global factor and its recalibration loop.

### Requirement: Recompute only self-derived capacities
**Reason**: Removed with the FMO capacity layer.
**Migration**: OmniRoute recomputes capacity from its own quota snapshot.

### Requirement: Shared-pool remaining is counted once across an account's endpoints
**Reason**: Shared-pool accounting is part of OmniRoute's quota/account model.
**Migration**: OmniRoute account-aware inventory counts shared pools once.
