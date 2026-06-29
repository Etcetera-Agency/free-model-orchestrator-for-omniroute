"""Unit coverage for the empty-`/v1/models` tombstone guard.

These exercise `_mark_missing_provider_models_removed` in isolation with a fake
transaction, so they do not need PostgreSQL.
"""

from fmo.scanner import _mark_missing_provider_models_removed


class _FakeResult:
    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _FakeTransaction:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        return _FakeResult()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeDatabase:
    def __init__(self, transaction):
        self._transaction = transaction

    def transaction(self):
        return self._transaction


class _FakeRepository:
    def __init__(self, transaction):
        self.database = _FakeDatabase(transaction)


class _FakeScanner:
    def __init__(self, transaction):
        self.repository = _FakeRepository(transaction)


def _run(*, live_models, provider_enabled):
    transaction = _FakeTransaction()
    _mark_missing_provider_models_removed(
        _FakeScanner(transaction),
        provider_id="p-1",
        live_models=live_models,
        provider_enabled=provider_enabled,
    )
    return transaction.statements


def test_enabled_provider_with_empty_models_does_not_tombstone():
    # A transient empty `/v1/models` response must not wipe the provider cache.
    assert _run(live_models=[], provider_enabled=True) == []


def test_enabled_provider_with_models_tombstones_absent_models():
    statements = _run(live_models=[{"id": "m-1"}], provider_enabled=True)
    assert len(statements) == 1
    sql, params = statements[0]
    assert "UPDATE provider_endpoints" in sql
    assert params == {"provider_id": "p-1", "model_ids": ["m-1"]}


def test_disabled_provider_with_empty_models_tombstones_all():
    statements = _run(live_models=[], provider_enabled=False)
    assert len(statements) == 1
    sql, params = statements[0]
    assert "UPDATE provider_endpoints" in sql
    assert params == {"provider_id": "p-1", "model_ids": []}
