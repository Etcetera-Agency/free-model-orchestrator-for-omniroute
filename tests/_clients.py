from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from fmo.aa_migration import MigrationProposalResponse
from fmo.hermes_inventory import InspectorForecastResponse, IntelligenceForecastResponse
from fmo.omniroute import OmniRouteRequestError
from fmo.quota_research import QuotaClaimResponse
from fmo.smart_review import ComboReviewResponse
from tests._fixtures import fixture_body

OPENAI_CHAT_COMPLETION_BODY = {
    "id": "chatcmpl-fmo-smoke",
    "object": "chat.completion",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
}

EMPTY_OPENAI_CHAT_COMPLETION_BODY = {
    "id": "chatcmpl-fmo-smoke-empty",
    "object": "chat.completion",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}],
}


class QuotaSearchClient:
    def __init__(self, answer="Provider gives 100 requests per day with hard stop."):
        self.answer = answer
        self.calls = []

    def post(self, path, payload):
        self.calls.append((path, payload))
        return {
            "answer": {"text": self.answer},
            "results": [{"title": "Docs", "url": "https://provider.example/free"}],
        }


class PipelineOpsClient(QuotaSearchClient):
    def __init__(self, *, probe_status=200, smoke_status=200, rollback_fails=False):
        super().__init__()
        self.probe_status = probe_status
        self.smoke_status = smoke_status
        self.rollback_fails = rollback_fails
        self.get_calls = []
        self.combos = {"fmo-routing_fast": ["old-endpoint"]}
        self.deleted_paths = []
        self.providers_body = deepcopy(fixture_body("omniroute_api_providers"))
        self.rate_limits_body = deepcopy(fixture_body("omniroute_api_rate_limits"))
        self.analytics_body = deepcopy(fixture_body("omniroute_api_usage_analytics"))
        self.quota_body = deepcopy(fixture_body("omniroute_api_usage_quota"))
        self.providers_body.setdefault("connections", []).append(
            {
                "id": "conn-provider-a",
                "provider": "provider-a",
                "enabled": True,
                "isActive": True,
                "upstream_account_id": "acct-provider-a",
                "status": "confirmed",
                "quota": 100,
            }
        )
        self.rate_limits_body.setdefault("connections", []).append(
            {
                "connectionId": "conn-provider-a",
                "provider": "provider-a",
                "enabled": True,
                "active": True,
                "remaining": 100,
            }
        )
        self.analytics_body.setdefault("byProvider", []).append(
            {"provider": "provider-a", "requests": 10, "successRatePct": 90, "avgLatencyMs": 120}
        )
        self.analytics_body.setdefault("byModel", []).append(
            {
                "provider": "provider-a",
                "model": "free-chat",
                "requests": 5,
                "successRatePct": 100,
                "avgLatencyMs": 80,
            }
        )
        self.quota_body.setdefault("providers", []).append(
            {
                "provider": "provider-a",
                "connectionId": "conn-provider-a",
                "quotaTotal": 200_000,
                "quotaUsed": 80_000,
                "quotaWindow": "day",
                "percentRemaining": 100,
                "resetAt": None,
            }
        )

    def put(self, path, payload, headers=None, idempotency_key=None):
        if path.startswith("/api/combos/"):
            combo_id = path.rsplit("/", 1)[-1]
            if self.rollback_fails and payload.get("models") == ["old-endpoint"]:
                raise RuntimeError("rollback failed")
            self.calls.append((path, payload, headers, idempotency_key))
            self.combos[combo_id] = list(payload["models"])
            return {"ok": True}
        raise AssertionError(f"unexpected PUT {path}")

    def post(self, path, payload, headers=None, idempotency_key=None):
        if path == "/v1/search":
            return super().post(path, payload)
        if path.startswith("/api/combos/"):
            raise AssertionError("combo updates must use PUT")
        if path == "/v1/chat/completions":
            self.calls.append((path, payload, headers, idempotency_key))
            if self.smoke_status >= 400:
                raise OmniRouteRequestError("POST", path, self.smoke_status)
            if self.smoke_status == 204:
                return EMPTY_OPENAI_CHAT_COMPLETION_BODY
            return OPENAI_CHAT_COMPLETION_BODY
        self.calls.append((path, payload, headers, idempotency_key))
        return {"status_code": self.probe_status, "content": "ok" if self.probe_status == 200 else ""}

    def delete(self, path):
        self.deleted_paths.append(path)
        raise AssertionError(f"unexpected DELETE {path}")

    def get(self, path):
        self.get_calls.append(path)
        if path == "/api/providers":
            return self.providers_body
        if path == "/api/rate-limits":
            return self.rate_limits_body
        if path == "/api/usage/analytics":
            return self.analytics_body
        if path == "/api/usage/quota":
            body = deepcopy(self.quota_body)
            body.setdefault("meta", {})["generatedAt"] = datetime.now(UTC).isoformat()
            return body
        if path == "/api/combos":
            return {"combos": [{"id": combo_id, "models": models} for combo_id, models in self.combos.items()]}
        raise AssertionError(f"unexpected GET {path}")


class PartiallyFailingQuotaSearchClient(PipelineOpsClient):
    def __init__(self, *, failing_model):
        super().__init__()
        self.failing_model = failing_model
        self.attempted_models = []

    def post(self, path, payload, headers=None, idempotency_key=None):
        if path == "/v1/search":
            query = str(payload["query"])
            model_id = query.split(" free tier quota for ", 1)[1].split(" today ", 1)[0]
            self.attempted_models.append(model_id)
            if model_id == self.failing_model:
                raise OmniRouteRequestError("POST", path, 503)
        return super().post(path, payload, headers=headers, idempotency_key=idempotency_key)


class MultiComboOpsClient(PipelineOpsClient):
    def __init__(self, repository, *, fail_smoke_for=None, restore_fail_for=None):
        super().__init__()
        self.repository = repository
        self.fail_smoke_for = set(fail_smoke_for or [])
        self.restore_fail_for = set(restore_fail_for or [])
        self.combos = {
            "fmo-a": ["old-a"],
            "fmo-b": ["old-b"],
        }
        self.applied_record_seen_before_second_mutation = False

    def put(self, path, payload, headers=None, idempotency_key=None):
        if path.startswith("/api/combos/"):
            combo_id = path.rsplit("/", 1)[-1]
            if combo_id == "fmo-b" and payload.get("models") != self._before_models(combo_id):
                self.applied_record_seen_before_second_mutation = self._applied_record_exists("fmo-a")
            if combo_id in self.restore_fail_for and payload.get("models") == self._before_models(combo_id):
                raise RuntimeError("restore failed")
        return super().put(path, payload, headers, idempotency_key)

    def post(self, path, payload, headers=None, idempotency_key=None):
        if path == "/v1/chat/completions":
            combo_id = payload["model"]
            self.calls.append((path, payload, headers, idempotency_key))
            if combo_id in self.fail_smoke_for:
                return EMPTY_OPENAI_CHAT_COMPLETION_BODY
            return OPENAI_CHAT_COMPLETION_BODY
        return super().post(path, payload, headers, idempotency_key)

    def _applied_record_exists(self, combo_id):
        with self.repository.database.transaction() as transaction:
            row = transaction.execute(
                """
                SELECT 1
                FROM combo_snapshots
                WHERE omniroute_combo_id = %(combo_id)s
                  AND phase = 'applied'
                LIMIT 1
                """,
                {"combo_id": combo_id},
            ).fetchone()
        return row is not None

    def _before_models(self, combo_id):
        return {"fmo-a": ["old-a"], "fmo-b": ["old-b"]}[combo_id]


class AccountDiscoveryOpsClient(PipelineOpsClient):
    def __init__(self, *, rate_limits_fail=False, connections=None):
        super().__init__()
        self.rate_limits_fail = rate_limits_fail
        self.connections = connections or [
            {
                "id": "conn-a",
                "provider": "provider-a",
                "enabled": True,
                "upstream_account_id": "shared-account",
                "status": "confirmed",
                "quota": 100,
            },
            {
                "id": "conn-b",
                "provider": "provider-a",
                "enabled": True,
                "upstream_account_id": "shared-account",
                "status": "confirmed",
                "quota": 100,
            },
        ]

    def get(self, path):
        self.get_calls.append(path)
        if path == "/api/providers":
            return {"connections": self.connections}
        if path == "/api/rate-limits":
            if self.rate_limits_fail:
                raise OmniRouteRequestError("GET", path, 500)
            return {
                "connections": [
                    {"connectionId": connection["id"], "provider": connection["provider"], "enabled": True}
                    for connection in self.connections
                ]
            }
        return super().get(path)


class RecordingLlmRuntime:
    def __init__(self, *, quota_amount=200.0, review_diffs=None, fail=False):
        self.quota_amount = quota_amount
        self.review_diffs = review_diffs or []
        self.fail = fail
        self.calls = []

    def complete(self, *, site, context, response_model):
        self.calls.append({"site": site.name, "context": context, "response_model": response_model.__name__})
        if self.fail:
            raise RuntimeError("llm unavailable")
        if response_model is QuotaClaimResponse:
            return response_model(
                metric="requests",
                amount=self.quota_amount,
                window="day",
                evidence=["https://llm.example/evidence"],
                hard_stop=True,
            )
        if response_model is ComboReviewResponse:
            return response_model(diffs=self.review_diffs)
        if response_model is InspectorForecastResponse:
            return response_model(
                role="routing_fast",
                expected_calls=25,
                average_input_tokens=100,
                average_output_tokens=50,
                confidence="medium",
            )
        if response_model is IntelligenceForecastResponse:
            return response_model(capability_axis="intelligence_index", tier="medium", confidence="medium")
        if response_model is MigrationProposalResponse:
            return response_model(
                index_version="4.2",
                roles={"routing_fast": {"metric": "intelligence_index", "threshold_value": 60}},
            )
        raise AssertionError(f"unexpected response model {response_model}")


class FakeOpenAIClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeInstructorCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response_model = kwargs["response_model"]
        if response_model is MigrationProposalResponse:
            return response_model(
                index_version="4.2",
                roles={"routing_fast": {"metric": "intelligence_index", "threshold_value": 60}},
            )
        return response_model(metric="requests", amount=1, window="day", evidence=["fixture"], hard_stop=True)


class FakeInstructorClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeInstructorCompletions()})()
