"""Minimal read-only HTTP client for the Hindsight API.

Deliberately dependency-light (urllib) so the facade has no transport surprises
in the MCP runtime. Only GET; never writes.
"""

from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HindsightError(RuntimeError):
    pass


class HindsightClient:
    def __init__(self, api_url: str, api_key: str = "", timeout: float = 30.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def get(self, path: str) -> Any:
        if not path.startswith("/"):
            raise HindsightError(f"refusing non-absolute path: {path}")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.api_url}{path}"
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except HTTPError as exc:
            raise HindsightError(f"GET {path} failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise HindsightError(f"GET {path} failed: {exc.reason}") from exc
        except OSError as exc:
            raise HindsightError(f"GET {path} failed: {exc}") from exc
        if not body:
            return None
        import json

        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HindsightError(f"GET {path} returned non-JSON") from exc

    def health(self) -> dict[str, Any]:
        payload = self.get("/health")
        if not isinstance(payload, dict):
            raise HindsightError("/health returned non-object")
        return payload
