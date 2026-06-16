import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg


@dataclass(frozen=True)
class CatalogSnapshot:
    fetch_success: bool
    fetched_at: datetime


@dataclass(frozen=True)
class StoredSnapshot:
    catalog_hash: str
    is_unchanged: bool


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
    return all(snapshot.fetch_success for snapshot in last_two) and last_two[0].fetched_at <= now - timedelta(minutes=5)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
