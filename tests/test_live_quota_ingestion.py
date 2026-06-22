from copy import deepcopy
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import pytest

from fmo.access import classify_access
from fmo.omniroute import OmniRouteClient
from fmo.quota_manager import QuotaFetchError, fail_closed_quota_evidence, fetch_live_quota_snapshot

from _fixtures import fixture_body


class _FixtureResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.headers = {}
        self._body = body

    def json(self):
        return self._body


class _QuotaTransport:
    def __init__(self, *, status_code=200, body=None):
        self.status_code = status_code
        self.body = body if body is not None else fixture_body("omniroute_api_usage_quota")
        self.requested_paths = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        path = urlsplit(url).path
        self.requested_paths.append(path)
        if path == "/api/usage/quota":
            return _FixtureResponse(self.status_code, self.body)
        raise AssertionError(f"unexpected quota request: {path}")


def _quota_body(*, generated_at: datetime) -> dict:
    body = deepcopy(fixture_body("omniroute_api_usage_quota"))
    body["meta"]["generatedAt"] = generated_at.isoformat().replace("+00:00", "Z")
    body["providers"][0].update(
        {
            "quotaTotal": 100,
            "quotaUsed": 25,
            "quotaWindow": "day",
            "resetAt": (generated_at + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
        }
    )
    return body


@pytest.mark.spec("quota-manager::Quota fetched at reset")
@pytest.mark.spec("quota-manager::Live token budget converted")
def test_live_quota_fetch_uses_omniroute_fixture_and_recomputes_remaining():
    now = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    body = _quota_body(generated_at=now - timedelta(minutes=2))
    target = body["providers"][0]
    transport = _QuotaTransport(body=body)
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    snapshot = fetch_live_quota_snapshot(client, now=now, max_age=timedelta(minutes=5), tokens_per_request=10)

    assert transport.requested_paths == ["/api/usage/quota"]
    quota = snapshot.quotas[f"{target['provider']}:{target['connectionId']}"]
    assert quota.limit == 10
    assert quota.remaining == 7.5
    assert quota.reset_at == now - timedelta(minutes=2) + timedelta(hours=6)


@pytest.mark.spec("quota-manager::Quota source unavailable")
def test_live_quota_stale_source_fails_closed():
    now = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    transport = _QuotaTransport(body=_quota_body(generated_at=now - timedelta(hours=2)))
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    with pytest.raises(QuotaFetchError) as exc:
        fetch_live_quota_snapshot(client, now=now, max_age=timedelta(minutes=5))

    evidence = fail_closed_quota_evidence(exc.value)
    decision = classify_access(evidence)
    assert exc.value.reason == "stale_data"
    assert decision.status == "unknown_excluded"


@pytest.mark.spec("quota-manager::Quota source unavailable")
def test_live_quota_unavailable_source_fails_closed():
    now = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    transport = _QuotaTransport(
        status_code=500,
        body=fixture_body("omniroute_api_usage_quota_http_500"),
    )
    client = OmniRouteClient(base_url="https://omniroute.test", api_key="manage-key", transport=transport)

    with pytest.raises(QuotaFetchError) as exc:
        fetch_live_quota_snapshot(client, now=now)

    evidence = fail_closed_quota_evidence(exc.value)
    decision = classify_access(evidence)
    assert exc.value.reason == "http_error"
    assert decision.status == "unknown_excluded"
