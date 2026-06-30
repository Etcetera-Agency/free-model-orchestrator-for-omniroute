import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx


@dataclass(frozen=True)
class VersionDecision:
    version: str
    can_read: bool
    can_apply: bool


class OmniRouteVersionGate:
    def __init__(self, known_apply_versions: set[str]):
        self.known_apply_versions = known_apply_versions

    def evaluate(self, version: str) -> VersionDecision:
        can_apply = version in self.known_apply_versions
        return VersionDecision(version=version, can_read=True, can_apply=can_apply)


class HttpxTransport:
    def request(self, method, url, headers=None, json=None, timeout=None):
        return httpx.request(method, url, headers=headers, json=json, timeout=timeout)


class OmniRouteRequestError(RuntimeError):
    def __init__(self, method: str, path: str, status_code: int) -> None:
        self.method = method
        self.path = path
        self.status_code = status_code
        super().__init__(f"OmniRoute {method} {path} failed with HTTP {status_code}")


@dataclass(frozen=True)
class OmniRouteHttpResponse:
    status_code: int
    body: dict
    text: str
    headers: dict[str, str]


class OmniRouteClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_get_retries: int = 1,
        transport=None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.api_key = api_key
        self.timeout = timeout
        self.max_get_retries = max_get_retries
        self.transport = transport or HttpxTransport()
        self.sleep = sleep

    def get(self, path: str) -> dict:
        return self._request("GET", path)

    def post(
        self,
        path: str,
        payload: dict,
        *,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        return self._request("POST", path, payload, headers=headers, idempotency_key=idempotency_key)

    def post_response(
        self,
        path: str,
        payload: dict,
        *,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> OmniRouteHttpResponse:
        try:
            response = self.transport.request(
                "POST",
                urljoin(self.base_url, path.lstrip("/")),
                headers=self._headers(headers=headers, idempotency_key=idempotency_key),
                json=payload,
                timeout=self.timeout,
            )
        except httpx.TransportError as exc:
            raise OmniRouteRequestError("POST", path, 0) from exc
        body: dict
        try:
            parsed = response.json()
            body = parsed if isinstance(parsed, dict) else {"value": parsed}
        except ValueError:
            body = {}
        return OmniRouteHttpResponse(
            status_code=response.status_code,
            body=body,
            text=response.text,
            headers=dict(response.headers),
        )

    def put(
        self,
        path: str,
        payload: dict,
        *,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        return self._request("PUT", path, payload, headers=headers, idempotency_key=idempotency_key)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        *,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        attempts = self.max_get_retries + 1 if method == "GET" else 1
        last_response = None
        for attempt in range(attempts):
            try:
                response = self.transport.request(
                    method,
                    urljoin(self.base_url, path.lstrip("/")),
                    headers=self._headers(headers=headers, idempotency_key=idempotency_key),
                    json=payload,
                    timeout=self.timeout,
                )
            except httpx.TransportError as exc:
                if method == "GET" and attempt + 1 < attempts:
                    self.sleep(_transient_backoff_seconds(attempt))
                    continue
                raise OmniRouteRequestError(method, path, 0) from exc
            last_response = response
            if response.status_code == 429 and method == "GET" and attempt + 1 < attempts:
                self.sleep(_retry_after_seconds(response.headers.get("Retry-After")))
                continue
            if _is_transient_get_status(method, response.status_code) and attempt + 1 < attempts:
                self.sleep(_transient_backoff_seconds(attempt))
                continue
            if 200 <= response.status_code < 300:
                try:
                    return response.json()
                except ValueError:
                    return {
                        "status_code": response.status_code,
                        "content": response.text,
                        "headers": dict(response.headers),
                    }
            break
        raise OmniRouteRequestError(method, path, last_response.status_code if last_response is not None else 0)

    def _headers(
        self,
        *,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        # AICODE-NOTE: Call-site headers supplement management auth/request IDs;
        # probe no-cache and apply idempotency must survive the same request.
        headers = dict(headers or {})
        headers["X-Request-Id"] = str(uuid.uuid4())
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers


def _is_transient_get_status(method: str, status_code: int) -> bool:
    return method == "GET" and status_code in {502, 503, 504}


def _transient_backoff_seconds(attempt: int) -> float:
    return min(1.0, 0.1 * (2**attempt))


def _retry_after_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        return 0.0
