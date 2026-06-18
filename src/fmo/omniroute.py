import time
import uuid
from dataclasses import dataclass
from typing import Callable
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

    def post(self, path: str, payload: dict) -> dict:
        return self._request("POST", path, payload)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        attempts = self.max_get_retries + 1 if method == "GET" else 1
        last_response = None
        for attempt in range(attempts):
            response = self.transport.request(
                method,
                urljoin(self.base_url, path.lstrip("/")),
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            last_response = response
            if response.status_code == 429 and method == "GET" and attempt + 1 < attempts:
                self.sleep(_retry_after_seconds(response.headers.get("Retry-After")))
                continue
            if 200 <= response.status_code < 300:
                return response.json()
            break
        raise OmniRouteRequestError(method, path, last_response.status_code)

    def _headers(self) -> dict[str, str]:
        headers = {"X-Request-Id": str(uuid.uuid4())}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _retry_after_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        return 0.0
