# combo-applier Specification

## REMOVED Requirements

### Requirement: Manage only fmo- combos
**Reason**: FMO no longer writes combos; the operator owns combos and FMO references existing `combo_id`s.
**Migration**: OmniRoute is the single writer of combo rows during materialization.

### Requirement: Transactional apply with smoke test
**Reason**: Combo apply moves to OmniRoute's atomic `db.transaction`.
**Migration**: OmniRoute applies a whole generation atomically (combos + marker + decision log).

### Requirement: Rollback on failure
**Reason**: No FMO-side combo write exists to roll back; OmniRoute fail-closes to the last good generation.
**Migration**: OmniRoute transaction rollback leaves the previous generation live.

### Requirement: Drift protection and anti-churn
**Reason**: Drift/anti-churn is handled by OmniRoute incumbency stability over the combos it owns.
**Migration**: OmniRoute stability margin + account stickiness replace FMO drift protection.

### Requirement: Apply preconditions evaluated at the entrypoint
**Reason**: Preconditions (combo exists, quota/probe safety) are evaluated inside OmniRoute materialization.
**Migration**: OmniRoute fails the generation on a missing combo and derives safety from request-path state.

### Requirement: Production apply invokes the real smoke path
**Reason**: No FMO apply path remains.
**Migration**: OmniRoute owns runtime validation; FMO validates only the published contract.

### Requirement: Apply stage derives quota and probe safety from persisted state
**Reason**: Quota/probe safety is request-path ground truth owned by OmniRoute.
**Migration**: OmniRoute reads live quota, cooldown, and lockout at materialization.

### Requirement: Multi-combo apply is all-or-nothing
**Reason**: Atomicity moves to OmniRoute's single-transaction generation apply.
**Migration**: OmniRoute commits all combo rows + marker + decision log together or none.

### Requirement: Rebalance only existing combos; never create or delete
**Reason**: This invariant now lives on the OmniRoute side (concept §17) and is enforced there.
**Migration**: OmniRoute fails the generation when a referenced combo is missing; it never creates/deletes.

### Requirement: Apply uses management combo API through the live bridge
**Reason**: FMO no longer calls the combo management API.
**Migration**: FMO calls `PUT /api/fmo/pools`; OmniRoute writes combos internally.

### Requirement: Public combo projection is never used for management apply
**Reason**: No FMO management apply remains.
**Migration**: N/A — removed with the apply path.
