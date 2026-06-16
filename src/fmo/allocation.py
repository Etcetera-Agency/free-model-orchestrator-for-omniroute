from dataclasses import dataclass


HEAVY_ROLES = {"research_scout", "health_reasoning", "cross_domain_orchestrator"}


@dataclass(frozen=True)
class RoleAllocation:
    endpoint_id: str
    pool: str
    demand: float


@dataclass(frozen=True)
class AllocationPlan:
    allocations: dict[str, RoleAllocation]
    pool_usage: dict[str, float]


@dataclass(frozen=True)
class Combo:
    role_id: str
    endpoints: list[str]
    strategy: str
    weights: None = None


@dataclass(frozen=True)
class PlanValidation:
    apply: bool
    reason: str | None = None
    role_status: str = "active"


def allocate_globally(roles: list[str], endpoints: list[dict], demand: dict[str, float]) -> AllocationPlan:
    pool_usage: dict[str, float] = {}
    heavy_primary_pools: set[str] = set()
    allocations: dict[str, RoleAllocation] = {}
    for role in roles:
        for endpoint in sorted(endpoints, key=lambda item: item["score"], reverse=True):
            pool = endpoint["pool"]
            if role in HEAVY_ROLES and pool in heavy_primary_pools:
                continue
            projected = pool_usage.get(pool, 0) + demand.get(role, 0)
            if projected <= endpoint["capacity"]:
                allocations[role] = RoleAllocation(endpoint_id=endpoint["id"], pool=pool, demand=demand.get(role, 0))
                pool_usage[pool] = projected
                if role in HEAVY_ROLES:
                    heavy_primary_pools.add(pool)
                break
    return AllocationPlan(allocations=allocations, pool_usage=pool_usage)


def build_priority_combo(role_id: str, endpoints: list[dict], *, per_pool_cap: int) -> Combo:
    ordered = [endpoint["id"] for endpoint in sorted(endpoints, key=lambda item: item["score"], reverse=True)[:per_pool_cap]]
    return Combo(role_id=role_id, endpoints=ordered, strategy="priority")


def validate_plan(pool_reports: dict[str, dict], *, role_has_primary: bool = True) -> PlanValidation:
    if not role_has_primary:
        return PlanValidation(apply=False, reason="no_primary", role_status="unavailable")
    for report in pool_reports.values():
        if report["capacity"] == 0 or report["usage"] / report["capacity"] > 1:
            return PlanValidation(apply=False, reason="oversubscribed")
    return PlanValidation(apply=True)


def keep_stable_order(current: list[str], scores: dict[str, float], *, threshold: float) -> list[str]:
    reordered = sorted(current, key=lambda endpoint_id: scores[endpoint_id], reverse=True)
    if reordered == current:
        return current
    improvement = scores[reordered[0]] - scores[current[0]]
    return reordered if improvement >= threshold else current
