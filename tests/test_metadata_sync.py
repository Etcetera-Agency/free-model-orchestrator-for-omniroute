import pytest

from fmo.artificial_analysis import AASnapshot
from fmo.metadata_sync import sync_external_metadata


@pytest.mark.spec("role-scorer::Artificial Analysis metadata fetch")
def test_sync_external_metadata_uses_free_artificial_analysis_endpoint(monkeypatch):
    calls = []

    monkeypatch.setattr("fmo.metadata_sync.sync_models_dev_candidates", lambda: {})

    def fetch_free_snapshot(*, api_key):
        calls.append(api_key)
        return AASnapshot(index_version="4.1", models=())

    monkeypatch.setattr("fmo.metadata_sync.fetch_artificial_analysis_free_snapshot", fetch_free_snapshot)

    result = sync_external_metadata(aa_api_key="aa-secret")

    assert result.aa_snapshot.index_version == "4.1"
    assert calls == ["aa-secret"]
