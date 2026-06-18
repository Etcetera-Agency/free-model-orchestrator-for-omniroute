import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg

from fmo.omniroute import OmniRouteRequestError


@dataclass(frozen=True)
class CatalogSnapshot:
    fetch_success: bool
    fetched_at: datetime


@dataclass(frozen=True)
class StoredSnapshot:
    catalog_hash: str
    is_unchanged: bool


@dataclass(frozen=True)
class CatalogFetchError(Exception):
    source: str
    reason: str
    status_code: int | None = None


@dataclass(frozen=True)
class CatalogScanResult:
    provider_slug: str
    fetch_status: str
    model_count: int
    snapshot: StoredSnapshot
    error: CatalogFetchError | None = None


@dataclass(frozen=True)
class ProviderEndpoint:
    id: str
    lifecycle_status: str
    access_status: str
    probe_status: str


@dataclass(frozen=True)
class CatalogEvent:
    kind: str
    model_id: str


class CatalogScanner:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def upsert_provider_account(
        self,
        *,
        omniroute_instance_id: str,
        provider_slug: str,
        provider_type: str,
        account_ref: str,
    ) -> tuple[str, str]:
        with psycopg.connect(self.database_url) as connection:
            provider_id = connection.execute(
                """
                INSERT INTO providers (omniroute_instance_id, omniroute_provider_id, provider_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (omniroute_instance_id, omniroute_provider_id)
                DO UPDATE SET provider_type = EXCLUDED.provider_type, last_seen_at = now()
                RETURNING id
                """,
                (omniroute_instance_id, provider_slug, provider_type),
            ).fetchone()[0]
            account_id = connection.execute(
                """
                INSERT INTO provider_accounts (provider_id, external_account_ref)
                VALUES (%s, %s)
                RETURNING id
                """,
                (provider_id, account_ref),
            ).fetchone()[0]
            connection.commit()
        return str(provider_id), str(account_id)

    def store_snapshot(self, *, provider_id: str, catalog: dict[str, Any], fetch_status: str) -> StoredSnapshot:
        catalog_hash = _stable_hash(catalog)
        with psycopg.connect(self.database_url) as connection:
            previous = connection.execute(
                """
                SELECT catalog_hash
                FROM provider_catalog_snapshots
                WHERE provider_id = %s AND fetch_status = 'success'
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                (provider_id,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO provider_catalog_snapshots (provider_id, catalog_hash, raw_payload, model_count, fetch_status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (provider_id, catalog_hash) DO NOTHING
                """,
                (provider_id, catalog_hash, json.dumps(catalog), len(catalog.get("models", [])), fetch_status),
            )
            connection.commit()
        return StoredSnapshot(catalog_hash=catalog_hash, is_unchanged=bool(previous and previous[0] == catalog_hash))

    def upsert_endpoint(self, provider_account_id: str, provider_model_id: str, model_type: str = "chat") -> ProviderEndpoint:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                INSERT INTO provider_endpoints (
                    provider_account_id,
                    provider_model_id,
                    model_type,
                    lifecycle_status,
                    access_status,
                    probe_status
                )
                VALUES (%s, %s, %s, 'discovered', 'access_pending', 'not_run')
                ON CONFLICT (provider_account_id, provider_model_id, model_type)
                DO UPDATE SET last_seen_at = now()
                RETURNING id, lifecycle_status, access_status, probe_status
                """,
                (provider_account_id, provider_model_id, model_type),
            ).fetchone()
            connection.commit()
        return ProviderEndpoint(id=str(row[0]), lifecycle_status=row[1], access_status=row[2], probe_status=row[3])


def diff_catalogs(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[CatalogEvent]:
    previous_ids = {item["id"] for item in previous}
    current_ids = {item["id"] for item in current}
    events = [CatalogEvent("provider_model_added", model_id) for model_id in sorted(current_ids - previous_ids)]
    events.extend(CatalogEvent("provider_model_removed", model_id) for model_id in sorted(previous_ids - current_ids))
    return events


def should_mark_removed(snapshots: list[CatalogSnapshot], now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if len(snapshots) < 2:
        return False
    last_two = snapshots[-2:]
    return all(snapshot.fetch_success for snapshot in last_two) and last_two[-1].fetched_at <= now - timedelta(minutes=5)


def scan_live_omniroute_catalogs(
    scanner: CatalogScanner,
    client: Any,
    *,
    omniroute_instance_id: str,
) -> dict[str, CatalogScanResult]:
    provider_accounts = _fetch_provider_accounts(client)
    provider_ids = _upsert_provider_accounts(scanner, omniroute_instance_id, provider_accounts)
    try:
        catalogs = _fetch_models_catalogs(client)
    except CatalogFetchError as exc:
        return {
            provider_slug: _store_failed_catalog(scanner, provider_slug, provider_id, exc)
            for provider_slug, provider_id in provider_ids.items()
        }

    results = {}
    for provider_slug, provider_id in provider_ids.items():
        catalog = {"models": catalogs.get(provider_slug, [])}
        snapshot = scanner.store_snapshot(provider_id=provider_id, catalog=catalog, fetch_status="success")
        for account_id in _account_ids_for_provider(scanner, omniroute_instance_id, provider_slug):
            for model in catalog["models"]:
                scanner.upsert_endpoint(account_id, model["id"])
        results[provider_slug] = CatalogScanResult(
            provider_slug=provider_slug,
            fetch_status="success",
            model_count=len(catalog["models"]),
            snapshot=snapshot,
        )
    return results


def _fetch_provider_accounts(client: Any) -> list[dict[str, Any]]:
    try:
        payload = client.get("/api/providers")
    except OmniRouteRequestError as exc:
        raise CatalogFetchError("omniroute_catalog", "http_error", exc.status_code) from exc
    except Exception as exc:
        raise CatalogFetchError("omniroute_catalog", "network_error") from exc
    connections = payload.get("connections") if isinstance(payload, dict) else None
    if not isinstance(connections, list):
        raise CatalogFetchError("omniroute_catalog", "invalid_payload")
    return [connection for connection in connections if isinstance(connection, dict) and connection.get("provider")]


def _upsert_provider_accounts(
    scanner: CatalogScanner,
    omniroute_instance_id: str,
    provider_accounts: list[dict[str, Any]],
) -> dict[str, str]:
    provider_ids = {}
    for account in provider_accounts:
        provider_slug = str(account["provider"])
        provider_id, _account_id = scanner.upsert_provider_account(
            omniroute_instance_id=omniroute_instance_id,
            provider_slug=provider_slug,
            provider_type=str(account.get("authType") or "unknown"),
            account_ref=str(account.get("id") or account.get("name") or provider_slug),
        )
        provider_ids[provider_slug] = provider_id
    return provider_ids


def _fetch_models_catalogs(client: Any) -> dict[str, list[dict[str, Any]]]:
    try:
        payload = client.get("/v1/models")
    except OmniRouteRequestError as exc:
        raise CatalogFetchError("omniroute_catalog", "http_error", exc.status_code) from exc
    except Exception as exc:
        raise CatalogFetchError("omniroute_catalog", "network_error") from exc
    models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise CatalogFetchError("omniroute_catalog", "invalid_payload")

    catalogs: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        if not isinstance(model, dict) or not isinstance(model.get("id"), str):
            raise CatalogFetchError("omniroute_catalog", "invalid_payload")
        provider_slug = _catalog_provider_slug(model)
        if provider_slug:
            catalogs.setdefault(provider_slug, []).append(model)
    return catalogs


def _catalog_provider_slug(model: dict[str, Any]) -> str | None:
    owned_by = model.get("owned_by")
    if isinstance(owned_by, str) and owned_by:
        return owned_by
    model_id = model.get("id")
    if isinstance(model_id, str) and "/" in model_id:
        return model_id.split("/", 1)[0]
    return None


def _account_ids_for_provider(scanner: CatalogScanner, omniroute_instance_id: str, provider_slug: str) -> list[str]:
    with psycopg.connect(scanner.database_url) as connection:
        rows = connection.execute(
            """
            SELECT pa.id
            FROM provider_accounts pa
            JOIN providers p ON p.id = pa.provider_id
            WHERE p.omniroute_instance_id = %s AND p.omniroute_provider_id = %s
            """,
            (omniroute_instance_id, provider_slug),
        ).fetchall()
    return [str(row[0]) for row in rows]


def _store_failed_catalog(
    scanner: CatalogScanner,
    provider_slug: str,
    provider_id: str,
    error: CatalogFetchError,
) -> CatalogScanResult:
    snapshot = scanner.store_snapshot(
        provider_id=provider_id,
        catalog={"error": {"source": error.source, "reason": error.reason, "status_code": error.status_code}},
        fetch_status="error",
    )
    return CatalogScanResult(
        provider_slug=provider_slug,
        fetch_status="error",
        model_count=0,
        snapshot=snapshot,
        error=error,
    )


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
