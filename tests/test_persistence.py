import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest

from fmo.db import MigrationRunner
from fmo.persistence import Database, Repository

_PUBLIC_PERSISTENCE_CLASSES = {
    "AuditRepository",
    "Database",
    "LockRepository",
    "PublishedGenerationRepository",
    "Repository",
    "RoleConsumerRepository",
    "RoleRepository",
    "RunRepository",
}


@pytest.mark.spec("system-architecture::Persistence public API stays import-stable")
def test_persistence_public_api_reexports_repository_classes():
    module = importlib.import_module("fmo.persistence")

    for name in sorted(_PUBLIC_PERSISTENCE_CLASSES):
        exported = getattr(module, name)
        assert inspect.isclass(exported), name


@pytest.mark.spec("system-architecture::Persistence layer is split into per-aggregate modules")
def test_persistence_layer_is_package_with_current_aggregate_modules():
    package = importlib.import_module("fmo.persistence")

    assert hasattr(package, "__path__")
    modules = {item.name for item in pkgutil.iter_modules(package.__path__)}
    assert {
        "_base",
        "audit",
        "lock",
        "published_generation",
        "role",
        "role_consumer",
        "run",
    }.issubset(modules)
    assert {
        "account",
        "canonical_model",
        "catalog",
        "endpoint",
        "external_metadata",
        "probe",
        "provider",
        "registry",
        "score",
        "snapshot",
    }.isdisjoint(modules)

    base = importlib.import_module("fmo.persistence._base")
    assert base.Database is Database
    assert base.Repository is Repository
    for helper in ("_one", "_optional", "_many", "_jsonb", "_content_hash"):
        assert callable(getattr(base, helper))


@pytest.fixture()
def repository(postgres_url):
    MigrationRunner(postgres_url).apply_schema(Path("reference/db/schema.sql"))
    return Repository(Database(postgres_url))


@pytest.mark.spec("persistence::Failed write rolls back")
def test_failed_transaction_rolls_back_rows(repository):
    with pytest.raises(RuntimeError, match="boom"):
        with repository.database.transaction() as transaction:
            repository.runs.create(
                transaction,
                run_type="full",
                trigger="manual",
                status="running",
                code_version="test",
                config_hash="cfg",
            )
            raise RuntimeError("boom")

    with repository.database.transaction() as transaction:
        assert repository.runs.list(transaction) == []


@pytest.mark.spec("persistence::Committed write is durable")
def test_committed_transaction_is_visible_to_new_connection(repository):
    with repository.database.transaction() as transaction:
        run = repository.runs.create(
            transaction,
            run_type="full",
            trigger="manual",
            status="running",
            code_version="test",
            config_hash="cfg",
        )

    with repository.database.transaction() as transaction:
        assert repository.runs.get(transaction, run["id"]) == run


@pytest.mark.spec("data-model::Role reference type")
@pytest.mark.spec("data-model::Repository is the only writer")
def test_current_domain_repository_round_trips(repository):
    with repository.database.transaction() as transaction:
        role = repository.roles.upsert(
            transaction,
            role_id="coder",
            requirements={"min_context": 8192},
            expected_load={"requests": 1},
            criticality=5,
        )
        consumer = repository.role_consumers.upsert(
            transaction,
            role_id=role["id"],
            consumer_type="agent_profile",
            consumer_key="agent:coder",
            cadence="manual",
            calls_per_run=1,
            source_hash="hash",
        )
        generation = repository.published_generations.upsert(
            transaction,
            generation="2026-06-29T00:00:00Z",
            payload_hash="payload",
            payload_json={"pools": []},
            status="acked",
        )
        audit = repository.audit.record(
            transaction,
            entity_type="pool",
            entity_id=role["id"],
            action="published",
            after_json={"generation": generation["generation"]},
            reason_codes=["test"],
        )

    with repository.database.transaction() as transaction:
        assert repository.roles.get(transaction, role["id"]) == role
        assert repository.role_consumers.get(transaction, consumer["id"]) == consumer
        assert repository.published_generations.get(transaction, generation["generation"], generation["payload_hash"])
        assert repository.audit.get(transaction, audit["id"]) == audit


@pytest.mark.spec("system-architecture::Row access helpers are defined once in the persistence base")
def test_row_access_helpers_have_one_persistence_definition():
    helper_names = {"_one", "_optional", "_many", "_jsonb", "_content_hash"}
    definitions: dict[str, list[Path]] = {name: [] for name in helper_names}

    for path in Path("src/fmo").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for name in helper_names:
            if f"def {name}(" in source:
                definitions[name].append(path)

    assert definitions == {name: [Path("src/fmo/persistence/_base.py")] for name in helper_names}
