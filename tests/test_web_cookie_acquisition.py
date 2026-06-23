import pytest

from _fixtures import fixture_body
from fmo.web_cookie import (
    WebCookieEndpoint,
    acquire_web_cookie_sessions,
    classify_web_cookie_probe,
)


def _web_cookie_fixture():
    return fixture_body("omniroute_web_cookie_sessions")


@pytest.mark.spec("web-cookie-candidates::Configured session acquired and probed")
def test_acquisition_loads_only_explicit_eligible_web_cookie_session_sources():
    body = _web_cookie_fixture()
    endpoints = [
        WebCookieEndpoint(id="chatgpt-web:gpt-4o-mini", model="gpt-4o-mini", source="connection"),
        WebCookieEndpoint(id="chatgpt-web:gpt-4o", model="gpt-4o", source="connection"),
        WebCookieEndpoint(id="claude-web:claude-3-5-haiku", model="claude-3-5-haiku", source="manual"),
        WebCookieEndpoint(id="perplexity-web:sonar", model="sonar", source="manual"),
        WebCookieEndpoint(id="openai:gpt-4o-mini", model="gpt-4o-mini", source="connection"),
        WebCookieEndpoint(id="unconfigured-web:mistral-large", model="mistral-large", source="manual"),
    ]

    acquisitions = acquire_web_cookie_sessions(
        endpoints=endpoints,
        configured_sources=body["sessionSources"],
        eligible_source_ids={
            "browser-chatgpt-default",
            "browser-chatgpt-expired",
            "browser-claude-challenge",
            "manual-perplexity-login",
            "connection-openai-api-key",
        },
        probe_responses=body["probeResponses"],
    )

    assert [acquisition.source_id for acquisition in acquisitions] == [
        "browser-chatgpt-default",
        "browser-chatgpt-expired",
        "browser-claude-challenge",
        "manual-perplexity-login",
        "connection-openai-api-key",
    ]
    assert "unconfigured-web:mistral-large" not in {acquisition.endpoint.id for acquisition in acquisitions}
    assert acquisitions[0].confirmed_usable is True
    assert acquisitions[-1].failure_mode == "unsupported_auth"


@pytest.mark.spec("web-cookie-candidates::Configured session acquired and probed")
def test_acquisition_respects_eligible_source_allowlist():
    body = _web_cookie_fixture()
    acquisitions = acquire_web_cookie_sessions(
        endpoints=[WebCookieEndpoint(id="chatgpt-web:gpt-4o-mini", model="gpt-4o-mini", source="connection")],
        configured_sources=body["sessionSources"],
        eligible_source_ids=set(),
        probe_responses=body["probeResponses"],
    )

    assert acquisitions == []


@pytest.mark.spec("web-cookie-candidates::Failure mode separated")
def test_probe_classifies_expired_challenge_login_and_unsupported_auth_modes():
    body = _web_cookie_fixture()
    sources_by_id = {source["source_id"]: source for source in body["sessionSources"]}
    probes_by_endpoint = {probe["endpoint_id"]: probe for probe in body["probeResponses"]}

    cases = {
        "browser-chatgpt-expired": "expired",
        "browser-claude-challenge": "challenge",
        "manual-perplexity-login": "login_required",
        "connection-openai-api-key": "unsupported_auth",
    }
    for source_id, expected_failure in cases.items():
        source = sources_by_id[source_id]
        probe = probes_by_endpoint[source["endpoint_id"]]
        outcome = classify_web_cookie_probe(
            session=source["session"],
            response_text=probe["response_text"],
            http_status=probe["http_status"],
            auth_type=source["auth_type"],
        )

        assert outcome.passed is False
        assert outcome.failure_mode == expected_failure


@pytest.mark.spec("web-cookie-candidates::Usable session becomes fallback capacity")
def test_confirmed_usable_session_is_reduced_weight_fallback_and_failed_session_unused():
    body = _web_cookie_fixture()
    acquisitions = acquire_web_cookie_sessions(
        endpoints=[
            WebCookieEndpoint(id="chatgpt-web:gpt-4o-mini", model="gpt-4o-mini", source="connection"),
            WebCookieEndpoint(id="chatgpt-web:gpt-4o", model="gpt-4o", source="connection"),
        ],
        configured_sources=body["sessionSources"],
        eligible_source_ids={"browser-chatgpt-default", "browser-chatgpt-expired"},
        probe_responses=body["probeResponses"],
        quota_known_by_endpoint={"chatgpt-web:gpt-4o-mini": False},
    )

    usable, expired = acquisitions
    assert usable.confirmed_usable is True
    assert usable.allocation_policy is not None
    assert usable.allocation_policy.fallback_only is True
    assert usable.allocation_policy.primary_allowed is False
    assert usable.allocation_policy.guaranteed_capacity == 0
    assert 0 < usable.allocation_policy.allocation_weight < 1
    assert expired.confirmed_usable is False
    assert expired.allocation_policy is None
