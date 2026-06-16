from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QuotaPool:
    pool_key: str
    independence_status: str
    capacity: float


def group_quota_pools(
    connections: list[dict[str, Any]],
    *,
    previous_pools: dict[str, str] | None = None,
    rate_limits_available: bool = True,
) -> dict[str, QuotaPool]:
    previous_pools = previous_pools or {}
    pools: dict[str, QuotaPool] = {}
    for connection in connections:
        connection_id = str(connection["id"])
        pool_key = _pool_key(connection, previous_pools, rate_limits_available)
        status = connection.get("status", "assumed_shared")
        capacity = float(connection.get("quota", 0)) if status == "confirmed" else 0.0
        existing = pools.get(pool_key)
        if existing:
            pools[pool_key] = QuotaPool(
                pool_key=pool_key,
                independence_status=_merge_status(existing.independence_status, status),
                capacity=max(existing.capacity, capacity),
            )
        else:
            pools[pool_key] = QuotaPool(pool_key=pool_key, independence_status=status, capacity=capacity)
        pools[connection_id] = QuotaPool(pool_key=pool_key, independence_status=status, capacity=0.0)
    return pools


def usable_capacity(pools: dict[str, QuotaPool]) -> float:
    unique = {key: pool for key, pool in pools.items() if key == pool.pool_key}
    return sum(pool.capacity for pool in unique.values() if pool.independence_status == "confirmed")


def _pool_key(connection: dict[str, Any], previous_pools: dict[str, str], rate_limits_available: bool) -> str:
    connection_id = str(connection["id"])
    if not rate_limits_available and connection_id in previous_pools:
        return previous_pools[connection_id]
    for key in ("manual_pool_key", "upstream_account_id", "rate_limit_account_id", "credential_fingerprint"):
        if connection.get(key):
            return str(connection[key])
    return f"{connection.get('provider', 'unknown')}:shared"


def _merge_status(left: str, right: str) -> str:
    if left == right:
        return left
    return "unknown"
