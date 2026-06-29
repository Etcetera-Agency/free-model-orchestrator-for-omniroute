# quota-attribution Specification

## REMOVED Requirements

### Requirement: quota_pool is optional
**Reason**: FMO no longer stores quota attribution groups or quota pools.
**Migration**: OmniRoute owns quota attribution and pool ownership.

### Requirement: Capacity by attribution status
**Reason**: FMO no longer computes capacity from quota attribution status.
**Migration**: OmniRoute solve owns capacity and shared-dependency accounting.
