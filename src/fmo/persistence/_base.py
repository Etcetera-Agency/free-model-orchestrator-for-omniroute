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
    from .audit import AuditRepository
    from .lock import LockRepository
    from .published_generation import PublishedGenerationRepository
    from .role import RoleRepository
    from .role_consumer import RoleConsumerRepository
    from .run import RunRepository


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
    roles: RoleRepository = field(init=False)
    role_consumers: RoleConsumerRepository = field(init=False)
    audit: AuditRepository = field(init=False)
    locks: LockRepository = field(init=False)
    published_generations: PublishedGenerationRepository = field(init=False)

    def __post_init__(self) -> None:
        from .audit import AuditRepository
        from .lock import LockRepository
        from .published_generation import PublishedGenerationRepository
        from .role import RoleRepository
        from .role_consumer import RoleConsumerRepository
        from .run import RunRepository

        object.__setattr__(self, "runs", RunRepository())
        object.__setattr__(self, "roles", RoleRepository())
        object.__setattr__(self, "role_consumers", RoleConsumerRepository())
        object.__setattr__(self, "audit", AuditRepository())
        object.__setattr__(self, "locks", LockRepository())
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


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
