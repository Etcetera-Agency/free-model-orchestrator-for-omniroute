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


FREE_ROUTER_ACCESS = {"free_unlimited", "free_quota_available", "free_promotional_available"}


def build_priority_combo(
    role_id: str,
    endpoints: list[dict],
    *,
    per_pool_cap: int,
    demand: float,
    pool_usage: dict[str, float],
    reserved_endpoint_id: str | None,
    auto_router_tail: list[str] | tuple[str, ...] = (),
    required_capabilities: set[str] | None = None,
    minimum_context: int = 0,
) -> Combo:
    ordered = []
    used_pools = set()
    scored_endpoints = [endpoint for endpoint in endpoints if not endpoint.get("is_router")]
    for endpoint in sorted(scored_endpoints, key=lambda item: item["score"]):
        pool = endpoint.get("pool")
        if role_id in HEAVY_ROLES and pool is not None and pool in used_pools:
            continue
        already_reserved = endpoint["id"] == reserved_endpoint_id
        if pool is not None and not already_reserved and pool_usage.get(pool, 0) + demand > endpoint["capacity"]:
            continue
        ordered.append(endpoint["id"])
        if pool is not None:
            used_pools.add(pool)
            if not already_reserved:
                pool_usage[pool] = pool_usage.get(pool, 0) + demand
        if len(ordered) == per_pool_cap:
            break
    router_order = {model_id.lower(): index for index, model_id in enumerate(auto_router_tail)}
    routers = [endpoint for endpoint in endpoints if endpoint.get("is_router")]
    routers = sorted(routers, key=lambda item: router_order.get(str(item["id"]).lower(), len(router_order)))
    required = required_capabilities or set()
    for endpoint in routers:
        if _router_tail_eligible(endpoint, required_capabilities=required, minimum_context=minimum_context):
            ordered.append(endpoint["id"])
    return Combo(role_id=role_id, endpoints=ordered, strategy="priority")


def _router_tail_eligible(endpoint: dict, *, required_capabilities: set[str], minimum_context: int) -> bool:
    if endpoint.get("access") not in FREE_ROUTER_ACCESS:
        return False
    if endpoint.get("basic_probe") is not True:
        return False
    if endpoint.get("quota", 0) <= 0:
        return False
    if endpoint.get("breaker") != "closed":
        return False
    if not required_capabilities.issubset(set(endpoint.get("input", ()))):
        return False
    return endpoint.get("effective_context_window", 0) >= minimum_context


def validate_plan(pool_reports: dict[str, dict], *, role_has_primary: bool = True) -> PlanValidation:
    if not role_has_primary:
        return PlanValidation(apply=False, reason="no_primary", role_status="unavailable")
    for report in pool_reports.values():
        if report["capacity"] == 0 or report["usage"] / report["capacity"] > 1:
            return PlanValidation(apply=False, reason="oversubscribed")
    return PlanValidation(apply=True)


def keep_stable_order(current: list[str], scores: dict[str, float], *, threshold: float) -> list[str]:
    if any(endpoint_id not in scores for endpoint_id in current):
        return current
    reordered = sorted(current, key=lambda endpoint_id: scores[endpoint_id], reverse=True)
    if reordered == current:
        return current
    improvement = scores[reordered[0]] - scores[current[0]]
    return reordered if improvement >= threshold else current
