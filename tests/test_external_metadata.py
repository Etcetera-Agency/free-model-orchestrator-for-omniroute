import pytest

from fmo.aa_migration import detect_index_change
from fmo.artificial_analysis import ARTIFICIAL_ANALYSIS_URL, fetch_artificial_analysis_snapshot
from fmo.external_metadata import ExternalMetadataError


class FakeResponse:
    def __init__(self, status_code, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeHttpClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


def test_artificial_analysis_fetcher_requires_api_key_and_sends_x_api_key():
    payload = {"intelligence_index_version": 4.1, "data": []}
    client = FakeHttpClient(FakeResponse(200, payload))

    snapshot = fetch_artificial_analysis_snapshot(client=client, api_key="aa-secret", timeout=9)

    assert snapshot.index_version == "4.1"
    assert client.calls == [
        (
            ARTIFICIAL_ANALYSIS_URL,
            {"headers": {"x-api-key": "aa-secret"}, "timeout": 9},
        )
    ]


def test_artificial_analysis_missing_api_key_fails_before_network():
    client = FakeHttpClient(FakeResponse(200, {"intelligence_index_version": "4.1", "data": []}))

    with pytest.raises(ExternalMetadataError) as exc:
        fetch_artificial_analysis_snapshot(client=client, api_key="")

    assert exc.value.source == "artificial_analysis"
    assert exc.value.reason == "aa_api_key_required"
    assert client.calls == []


def test_artificial_analysis_error_does_not_expose_api_key():
    client = FakeHttpClient(FakeResponse(500, {"error": "down"}))

    with pytest.raises(ExternalMetadataError) as exc:
        fetch_artificial_analysis_snapshot(client=client, api_key="aa-secret")

    assert "aa-secret" not in str(exc.value)
    assert "x-api-key" not in str(exc.value)


def test_artificial_analysis_fetcher_normalizes_scoring_metrics():
    payload = {
        "intelligence_index_version": 4.1,
        "data": [
            {
                "slug": "provider-model-a",
                "evaluations": {
                    "artificial_analysis_intelligence_index": 80,
                    "artificial_analysis_coding_index": 70,
                    "artificial_analysis_agentic_index": 60,
                },
                "performance": {
                    "median_output_tokens_per_second": 100,
                    "median_end_to_end_seconds": 1.5,
                },
                "ignored": "raw-only",
            }
        ],
    }

    snapshot = fetch_artificial_analysis_snapshot(client=FakeHttpClient(FakeResponse(200, payload)), api_key="aa-secret")

    assert snapshot.index_version == "4.1"
    assert snapshot.models[0].model_id == "provider-model-a"
    assert snapshot.models[0].metrics == {
        "intelligence_index": 80,
        "coding_index": 70,
        "agentic_index": 60,
        "median_output_tokens_per_second": 100,
        "median_end_to_end_seconds": 1.5,
    }


def test_artificial_analysis_missing_metric_remains_missing():
    payload = {
        "intelligence_index_version": 4.1,
        "data": [
            {
                "slug": "provider-model-a",
                "evaluations": {"artificial_analysis_intelligence_index": 80},
            }
        ],
    }

    snapshot = fetch_artificial_analysis_snapshot(client=FakeHttpClient(FakeResponse(200, payload)), api_key="aa-secret")

    assert snapshot.models[0].metrics == {"intelligence_index": 80}
    assert "agentic_index" not in snapshot.models[0].metrics


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"data": []},
        {"intelligence_index_version": 4.1, "data": {}},
        {"intelligence_index_version": 4.1, "data": [{"evaluations": {"artificial_analysis_intelligence_index": 80}}]},
    ],
)
def test_artificial_analysis_rejects_invalid_payload_shape(payload):
    with pytest.raises(ExternalMetadataError) as exc:
        fetch_artificial_analysis_snapshot(client=FakeHttpClient(FakeResponse(200, payload)), api_key="aa-secret")

    assert exc.value.source == "artificial_analysis"
    assert exc.value.reason == "invalid_payload"


def test_artificial_analysis_invalid_json_and_network_errors_are_structured():
    for client in (
        FakeHttpClient(FakeResponse(200, json_error=ValueError("bad json"))),
        FakeHttpClient(error=TimeoutError("timeout")),
    ):
        with pytest.raises(ExternalMetadataError) as exc:
            fetch_artificial_analysis_snapshot(client=client, api_key="aa-secret")
        assert exc.value.source == "artificial_analysis"


def test_artificial_analysis_snapshot_index_version_feeds_migration_detection():
    payload = {
        "intelligence_index_version": 4.2,
        "data": [{"slug": "m", "evaluations": {"artificial_analysis_intelligence_index": 80}, "available": True}],
    }
    snapshot = fetch_artificial_analysis_snapshot(client=FakeHttpClient(FakeResponse(200, payload)), api_key="aa-secret")

    migration = detect_index_change(active_version="v1", fetched_version=snapshot.index_version, thresholds={"r": 40}, combos={"r": ["e1"]})

    assert migration.created is True


def test_artificial_analysis_fetch_failure_leaves_index_migration_unstarted():
    with pytest.raises(ExternalMetadataError):
        fetch_artificial_analysis_snapshot(client=FakeHttpClient(FakeResponse(503, {})), api_key="aa-secret")
