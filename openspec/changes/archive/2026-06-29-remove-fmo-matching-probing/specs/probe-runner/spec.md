# probe-runner Specification

## REMOVED Requirements

### Requirement: Probe only after free confirmation
**Reason**: Probing as a capacity/health source is replaced by OmniRoute's request path and reset-aware quota.
**Migration**: OmniRoute learns real outcomes from live traffic; no FMO probing.

### Requirement: Isolated probe request
**Reason**: No FMO probe path remains.
**Migration**: OmniRoute health/cooldown/breaker observe real requests.

### Requirement: Capability-gated suites
**Reason**: Capability checks move to OmniRoute's hard gates at materialization.
**Migration**: OmniRoute filters candidates by capability/context during inventory build.

### Requirement: Probe error handling and promotion
**Reason**: Promotion/observation of a candidate's ceiling becomes the OmniRoute place-first calibration canary.
**Migration**: OmniRoute seats a no-number candidate first and promotes it once its ceiling is observed.
