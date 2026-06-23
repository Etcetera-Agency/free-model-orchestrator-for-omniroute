from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from fmo.accounts import expand_account_scopes
from fmo.idempotency import utcnow
from fmo.omniroute import OmniRouteRequestError
from fmo.persistence import Repository


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
    def __init__(self, repository: Repository):
        self.repository = repository

    def upsert_provider_account(
        self,
        *,
        omniroute_instance_id: str,
        provider_slug: str,
        provider_type: str,
        account_ref: str,
    ) -> tuple[str, str]:
        with self.repository.database.transaction() as transaction:
            provider = self.repository.providers.upsert(
                transaction,
                omniroute_instance_id=omniroute_instance_id,
                omniroute_provider_id=provider_slug,
                provider_type=provider_type,
            )
            account = self.repository.provider_accounts.upsert(
                transaction,
                provider_id=provider["id"],
                omniroute_connection_id=account_ref,
                external_account_ref=account_ref,
            )
        return str(provider["id"]), str(account["id"])

    def upsert_provider_accounts(
        self,
        *,
        omniroute_instance_id: str,
        provider_accounts: list[dict[str, Any]],
    ) -> dict[str, tuple[str, list[str]]]:
        providers = {}
        with self.repository.database.transaction() as transaction:
            for account_payload in provider_accounts:
                provider_slug = str(account_payload["provider"])
                account_ref = str(account_payload.get("id") or account_payload.get("name") or provider_slug)
                external_ref = str(account_payload.get("external_account_ref") or account_ref)
                provider = self.repository.providers.upsert(
                    transaction,
                    omniroute_instance_id=omniroute_instance_id,
                    omniroute_provider_id=provider_slug,
                    provider_type=str(account_payload.get("authType") or "unknown"),
                )
                self.repository.provider_accounts.upsert(
                    transaction,
                    provider_id=provider["id"],
                    omniroute_connection_id=account_ref,
                    external_account_ref=external_ref,
                    metadata=account_payload,
                )
                accounts = self.repository.provider_accounts.list_for_provider(
                    transaction,
                    omniroute_instance_id=omniroute_instance_id,
                    omniroute_provider_id=provider_slug,
                )
                providers[provider_slug] = (str(provider["id"]), [str(account["id"]) for account in accounts])
        return providers

    def store_snapshot(self, *, provider_id: str, catalog: dict[str, Any], fetch_status: str) -> StoredSnapshot:
        with self.repository.database.transaction() as transaction:
            snapshot = self.repository.provider_catalogs.store_snapshot(
                transaction,
                provider_id=provider_id,
                catalog=catalog,
                fetch_status=fetch_status,
            )
        return StoredSnapshot(catalog_hash=snapshot["catalog_hash"], is_unchanged=snapshot["is_unchanged"])

    def upsert_endpoint(
        self, provider_account_id: str, provider_model_id: str, model_type: str = "chat"
    ) -> ProviderEndpoint:
        with self.repository.database.transaction() as transaction:
            endpoint = self.repository.provider_endpoints.upsert(
                transaction,
                provider_account_id=provider_account_id,
                provider_model_id=provider_model_id,
                model_type=model_type,
                lifecycle_status="discovered",
                access_status="access_pending",
                probe_status="not_run",
            )
        return ProviderEndpoint(
            id=str(endpoint["id"]),
            lifecycle_status=endpoint["lifecycle_status"],
            access_status=endpoint["access_status"],
            probe_status=endpoint["probe_status"],
        )


def diff_catalogs(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> list[CatalogEvent]:
    previous_ids = {item["id"] for item in previous}
    current_ids = {item["id"] for item in current}
    events = [CatalogEvent("provider_model_added", model_id) for model_id in sorted(current_ids - previous_ids)]
    events.extend(CatalogEvent("provider_model_removed", model_id) for model_id in sorted(previous_ids - current_ids))
    return events


def should_mark_removed(snapshots: list[CatalogSnapshot], now: datetime | None = None) -> bool:
    now = now or utcnow()
    if len(snapshots) < 2:
        return False
    last_two = snapshots[-2:]
    return all(snapshot.fetch_success for snapshot in last_two) and last_two[-1].fetched_at <= now - timedelta(
        minutes=5
    )


def scan_live_omniroute_catalogs(
    scanner: CatalogScanner,
    client: Any,
    *,
    omniroute_instance_id: str,
) -> dict[str, CatalogScanResult]:
    provider_accounts = _fetch_provider_accounts(client)
    provider_refs = scanner.upsert_provider_accounts(
        omniroute_instance_id=omniroute_instance_id,
        provider_accounts=provider_accounts,
    )
    try:
        catalogs = _fetch_models_catalogs(client)
    except CatalogFetchError as exc:
        return {
            provider_slug: _store_failed_catalog(scanner, provider_slug, provider_id, exc)
            for provider_slug, (provider_id, _account_ids) in provider_refs.items()
        }

    results = {}
    for provider_slug, (provider_id, account_ids) in provider_refs.items():
        catalog = {"models": catalogs.get(provider_slug, [])}
        snapshot = scanner.store_snapshot(provider_id=provider_id, catalog=catalog, fetch_status="success")
        for account_id in account_ids:
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
    provider_accounts = [
        connection for connection in connections if isinstance(connection, dict) and connection.get("provider")
    ]
    return expand_account_scopes(provider_accounts)


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
