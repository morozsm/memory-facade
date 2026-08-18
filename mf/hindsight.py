"""Minimal HTTP client for the Hindsight API.

Deliberately dependency-light (urllib) so the facade has no transport surprises
in the MCP runtime. Supports read-only GET plus one bounded POST (semantic
recall, which is read-only in effect and never mutates memory).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class HindsightError(RuntimeError):
    pass


class HindsightClient:
    def __init__(self, api_url: str, api_key: str = "", timeout: float = 30.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, body: Any | None = None) -> Any:
        if not path.startswith("/"):
            raise HindsightError(f"refusing non-absolute path: {path}")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = f"{self.api_url}{path}"
        request = Request(url, headers=headers, method=method, data=data)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raise HindsightError(f"{method} {path} failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise HindsightError(f"{method} {path} failed: {exc.reason}") from exc
        except OSError as exc:
            raise HindsightError(f"{method} {path} failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HindsightError(f"{method} {path} returned non-JSON") from exc

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def health(self) -> dict[str, Any]:
        payload = self.get("/health")
        if not isinstance(payload, dict):
            raise HindsightError("/health returned non-object")
        return payload

    def recall(
        self,
        bank_id: str,
        query: str,
        types: list[str] | None = None,
        budget: str = "mid",
        tags: list[str] | None = None,
        tags_match: str | None = None,
        max_tokens: int = 1200,
    ) -> Any:
        """POST semantic recall for one bank (read-only)."""
        encoded = quote(bank_id, safe="")
        path = f"/v1/default/banks/{encoded}/memories/recall"
        payload: dict[str, Any] = {
            "query": query,
            "budget": budget,
            "max_tokens": max_tokens,
        }
        if types:
            payload["types"] = types
        if tags:
            payload["tags"] = tags
            payload["tags_match"] = tags_match or "all_strict"
        return self._request("POST", path, payload)
