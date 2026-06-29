from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

Record = dict[str, Any]

if TYPE_CHECKING:
    from .account import ProviderAccountRepository
    from .allocation_plan import AllocationPlanRepository
    from .audit import AuditRepository
    from .canonical_model import CanonicalModelRepository
    from .catalog import ProviderCatalogRepository
    from .combo_snapshot import ComboSnapshotRepository
    from .endpoint import ProviderEndpointRepository
    from .external_metadata import ExternalMetadataRepository
    from .lock import LockRepository
    from .probe import ProbeRepository
    from .provider import ProviderRepository
    from .published_generation import PublishedGenerationRepository
    from .quota_rule import QuotaRuleRepository
    from .registry import FreeRegistryRepository
    from .role import RoleRepository
    from .role_consumer import RoleConsumerRepository
    from .run import RunRepository
    from .score import ScoreRepository
    from .snapshot import SnapshotRepository


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with psycopg.connect(self.database_url, row_factory=cast(Any, dict_row)) as connection:
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()


@dataclass(frozen=True)
class Repository:
    database: Database
    runs: RunRepository = field(init=False)
    providers: ProviderRepository = field(init=False)
    provider_accounts: ProviderAccountRepository = field(init=False)
    provider_catalogs: ProviderCatalogRepository = field(init=False)
    canonical_models: CanonicalModelRepository = field(init=False)
    provider_endpoints: ProviderEndpointRepository = field(init=False)
    free_registry: FreeRegistryRepository = field(init=False)
    snapshots: SnapshotRepository = field(init=False)
    quota_rules: QuotaRuleRepository = field(init=False)
    probes: ProbeRepository = field(init=False)
    roles: RoleRepository = field(init=False)
    role_consumers: RoleConsumerRepository = field(init=False)
    scores: ScoreRepository = field(init=False)
    allocation_plans: AllocationPlanRepository = field(init=False)
    combo_snapshots: ComboSnapshotRepository = field(init=False)
    audit: AuditRepository = field(init=False)
    locks: LockRepository = field(init=False)
    external_metadata: ExternalMetadataRepository = field(init=False)
    published_generations: PublishedGenerationRepository = field(init=False)

    def __post_init__(self) -> None:
        from .account import ProviderAccountRepository
        from .allocation_plan import AllocationPlanRepository
        from .audit import AuditRepository
        from .canonical_model import CanonicalModelRepository
        from .catalog import ProviderCatalogRepository
        from .combo_snapshot import ComboSnapshotRepository
        from .endpoint import ProviderEndpointRepository
        from .external_metadata import ExternalMetadataRepository
        from .lock import LockRepository
        from .probe import ProbeRepository
        from .provider import ProviderRepository
        from .published_generation import PublishedGenerationRepository
        from .quota_rule import QuotaRuleRepository
        from .registry import FreeRegistryRepository
        from .role import RoleRepository
        from .role_consumer import RoleConsumerRepository
        from .run import RunRepository
        from .score import ScoreRepository
        from .snapshot import SnapshotRepository

        object.__setattr__(self, "runs", RunRepository())
        object.__setattr__(self, "providers", ProviderRepository())
        object.__setattr__(self, "provider_accounts", ProviderAccountRepository())
        object.__setattr__(self, "provider_catalogs", ProviderCatalogRepository())
        object.__setattr__(self, "canonical_models", CanonicalModelRepository())
        object.__setattr__(self, "provider_endpoints", ProviderEndpointRepository())
        object.__setattr__(self, "free_registry", FreeRegistryRepository())
        object.__setattr__(self, "snapshots", SnapshotRepository())
        object.__setattr__(self, "quota_rules", QuotaRuleRepository())
        object.__setattr__(self, "probes", ProbeRepository())
        object.__setattr__(self, "roles", RoleRepository())
        object.__setattr__(self, "role_consumers", RoleConsumerRepository())
        object.__setattr__(self, "scores", ScoreRepository())
        object.__setattr__(self, "allocation_plans", AllocationPlanRepository())
        object.__setattr__(self, "combo_snapshots", ComboSnapshotRepository())
        object.__setattr__(self, "audit", AuditRepository())
        object.__setattr__(self, "locks", LockRepository())
        object.__setattr__(self, "external_metadata", ExternalMetadataRepository())
        object.__setattr__(self, "published_generations", PublishedGenerationRepository())


def _one(connection: Any, sql: str, params: dict[str, Any] | None = None) -> Record:
    row = connection.execute(sql, params or {}).fetchone()
    if row is None:
        raise LookupError("expected one row")
    return dict(row)


def _optional(connection: Any, sql: str, params: dict[str, Any] | None = None) -> Record | None:
    row = connection.execute(sql, params or {}).fetchone()
    return dict(row) if row is not None else None


def _many(connection: Any, sql: str, params: dict[str, Any] | None = None) -> list[Record]:
    return [dict(row) for row in connection.execute(sql, params or {}).fetchall()]


def _jsonb(value: Any) -> Jsonb | None:
    if value is None:
        return None
    return Jsonb(value)


def _trigger_type(cadence: str) -> str:
    if cadence.startswith("event"):
        return "event"
    if cadence == "continuous":
        return "continuous"
    if cadence == "manual":
        return "manual"
    if cadence.startswith("every"):
        return "interval"
    return "cron"


def _free_type(reasons: tuple[str, ...]) -> str:
    if "zero_cost" in reasons:
        return "zero_cost"
    if "multiple_signals" in reasons:
        return "multiple_signals"
    if reasons:
        return reasons[0]
    return "candidate"


def _split_model_id(model_id: str) -> tuple[str, str | None]:
    if "/" in model_id:
        provider_id, provider_model_id = model_id.split("/", 1)
        return provider_id, provider_model_id
    return "artificial_analysis", model_id


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
