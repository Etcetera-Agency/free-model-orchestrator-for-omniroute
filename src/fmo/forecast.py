from dataclasses import dataclass


@dataclass(frozen=True)
class ReservedDemand:
    base: float
    multiplier: float
    reserved: float


@dataclass(frozen=True)
class ColdStartDemand:
    value: float
    source: str


def aggregate_demand(agent_runs: dict[str, float], bindings: list[tuple[str, str, float]], dependencies: list[tuple[str, str, float]]) -> dict[str, float]:
    _reject_cycles(dependencies)
    demand: dict[str, float] = {}
    for agent_id, role_id, calls_per_run in bindings:
        demand[role_id] = demand.get(role_id, 0) + agent_runs.get(agent_id, 0) * calls_per_run
    changed = True
    while changed:
        changed = False
        for source_role, target_role, calls_per_source in dependencies:
            addition = demand.get(source_role, 0) * calls_per_source
            if addition and demand.get(target_role, 0) < addition:
                demand[target_role] = addition
                changed = True
    return demand


def protected_demand(*, expected: float, p95: float, peak_multiplier: float) -> float:
    return max(p95, expected * peak_multiplier)


def apply_historical_reserve(value: float, *, multiplier: float, already_applied: bool) -> ReservedDemand:
    base = value / multiplier if already_applied else value
    reserved = value if already_applied else value * multiplier
    return ReservedDemand(base=base, multiplier=multiplier, reserved=reserved)


def cold_start_demand(*, schedule: float | None, bootstrap: float | None, role_minimum: float, global_minimum: float) -> ColdStartDemand:
    if schedule is not None:
        return ColdStartDemand(schedule, "schedule")
    if bootstrap is not None:
        return ColdStartDemand(bootstrap, "bootstrap")
    return ColdStartDemand(max(role_minimum, global_minimum), "role_minimum")


def _reject_cycles(edges: list[tuple[str, str, float]]) -> None:
    graph: dict[str, list[str]] = {}
    for source, target, _ in edges:
        graph.setdefault(source, []).append(target)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("shared-role dependency cycle")
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, []):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
