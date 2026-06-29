from dataclasses import dataclass
from typing import Any

from fmo.omniroute import OmniRouteRequestError


@dataclass(frozen=True)
class QuotaPool:
    pool_key: str
    independence_status: str
    capacity: float


@dataclass(frozen=True)
class AccountFetchError(Exception):
    source: str
    reason: str
    status_code: int | None = None


@dataclass(frozen=True)
class AccountDiscoveryOutcome:
    connections: list[dict[str, Any]]
    pools: dict[str, QuotaPool]
    rate_limits_available: bool
    errors: list[AccountFetchError]


def group_quota_pools(
    connections: list[dict[str, Any]],
    *,
    previous_pools: dict[str, str] | None = None,
    rate_limits_available: bool = True,
) -> dict[str, QuotaPool]:
    previous_pools = previous_pools or {}
    pools: dict[str, QuotaPool] = {}
    for connection in expand_account_scopes(connections, rate_limits_available=rate_limits_available):
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


def expand_account_scopes(
    connections: list[dict[str, Any]],
    *,
    rate_limits_available: bool = True,
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for connection in connections:
        expanded.extend(_expand_connection_scopes(connection, rate_limits_available=rate_limits_available))
    return expanded


def connection_is_enabled(connection: dict[str, Any]) -> bool:
    if "isActive" in connection:
        return bool(connection["isActive"])
    if "enabled" in connection:
        return bool(connection["enabled"])
    return True


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


def _expand_connection_scopes(connection: dict[str, Any], *, rate_limits_available: bool) -> list[dict[str, Any]]:
    if connection.get("quota_scope_type") == "account_fingerprint":
        return [connection]
    fingerprints = _account_fingerprints(connection)
    if not fingerprints or not rate_limits_available:
        return [connection]

    # AICODE-NOTE: OmniRoute nested fingerprints are account-scope evidence;
    # do not multiply provider/model rows without it.
    parent_connection_id = str(connection["id"])
    provider = str(connection.get("provider") or "unknown")
    accounts = []
    for fingerprint in fingerprints:
        account = dict(connection)
        account["id"] = f"{parent_connection_id}#fingerprint:{fingerprint}"
        account["parent_connection_id"] = parent_connection_id
        account["credential_fingerprint"] = fingerprint
        account["external_account_ref"] = f"{provider}:fingerprint:{fingerprint}"
        account["manual_pool_key"] = f"{provider}:fingerprint:{fingerprint}"
        account["quota_scope_type"] = "account_fingerprint"
        account["quota_scope_key"] = fingerprint
        account["status"] = "confirmed"
        account["membership_reason"] = "account-fingerprint"
        accounts.append(account)
    return accounts


def _account_fingerprints(connection: dict[str, Any]) -> list[str]:
    provider_data = connection.get("providerSpecificData")
    if not isinstance(provider_data, dict):
        return []
    fingerprints = provider_data.get("fingerprints")
    if not isinstance(fingerprints, list):
        return []
    return sorted({str(fingerprint) for fingerprint in fingerprints if fingerprint})


def discover_live_accounts(
    client: Any,
    *,
    previous_pools: dict[str, str] | None = None,
) -> AccountDiscoveryOutcome:
    connections = _fetch_connections(client)
    errors: list[AccountFetchError] = []
    try:
        rate_limits = _fetch_rate_limits(client)
        rate_limits_available = True
    except AccountFetchError as exc:
        rate_limits = {}
        rate_limits_available = False
        errors.append(exc)

    normalized = _merge_connection_status(
        connections,
        rate_limits,
        rate_limits_available=rate_limits_available,
    )
    account_scopes = expand_account_scopes(normalized, rate_limits_available=rate_limits_available)
    pools = group_quota_pools(
        account_scopes,
        previous_pools=previous_pools,
        rate_limits_available=rate_limits_available,
    )
    return AccountDiscoveryOutcome(
        connections=account_scopes,
        pools=pools,
        rate_limits_available=rate_limits_available,
        errors=errors,
    )


def _fetch_connections(client: Any) -> list[dict[str, Any]]:
    payload = _client_get(client, "/api/providers")
    connections = payload.get("connections")
    if not isinstance(connections, list):
        raise AccountFetchError("omniroute_accounts", "invalid_payload")
    return [connection for connection in connections if isinstance(connection, dict)]


def _fetch_rate_limits(client: Any) -> dict[str, dict[str, Any]]:
    payload = _client_get(client, "/api/rate-limits")
    connections = payload.get("connections")
    if not isinstance(connections, list):
        raise AccountFetchError("omniroute_accounts", "invalid_payload")
    return {
        str(connection["connectionId"]): connection
        for connection in connections
        if isinstance(connection, dict) and connection.get("connectionId")
    }


def _merge_connection_status(
    connections: list[dict[str, Any]],
    rate_limits: dict[str, dict[str, Any]],
    *,
    rate_limits_available: bool,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for connection in connections:
        item = dict(connection)
        connection_id = str(item.get("id"))
        item["rate_limit"] = rate_limits.get(connection_id, {})
        item["status"] = _conservative_status(item, rate_limits_available=rate_limits_available)
        normalized.append(item)
    return normalized


def _conservative_status(connection: dict[str, Any], *, rate_limits_available: bool) -> str:
    if not rate_limits_available:
        return "assumed_shared"
    status = connection.get("status")
    return status if status in {"confirmed", "inferred", "assumed_shared", "unknown"} else "assumed_shared"


def _client_get(client: Any, path: str) -> dict[str, Any]:
    try:
        payload = client.get(path)
    except OmniRouteRequestError as exc:
        raise AccountFetchError("omniroute_accounts", "http_error", exc.status_code) from exc
    except Exception as exc:
        raise AccountFetchError("omniroute_accounts", "network_error") from exc
    if not isinstance(payload, dict):
        raise AccountFetchError("omniroute_accounts", "invalid_payload")
    return payload
