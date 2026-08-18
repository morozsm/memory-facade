"""Tests for mf.ping — the connectivity smoke tool (no network)."""

import pytest

from mf import server
from mf.hindsight import HindsightError


class FakeHindsight:
    """Injectable stand-in for HindsightClient with a scripted /health."""

    def __init__(self, health: dict | None = None, error: bool = False):
        self._health = health
        self._error = error
        self.calls = 0

    def health(self):
        self.calls += 1
        if self._error:
            raise HindsightError("boom")
        return self._health


def test_ping_reports_health():
    fake = FakeHindsight({"status": "healthy", "database": "connected"})
    result = server.make_ping(fake)()
    assert result["status"] == "healthy"
    assert result["database"] == "connected"
    assert result["api_url"] == "https://memory.msmsoft.net"
    assert fake.calls == 1


def test_ping_works_even_if_db_attrib_missing():
    fake = FakeHindsight({"status": "degraded"})
    result = server.make_ping(fake)()
    assert result["status"] == "degraded"
    assert result["database"] is None  # tolerant default


def test_ping_raises_on_hindsight_error():
    fake = FakeHindsight(error=True)
    with pytest.raises(HindsightError):
        server.make_ping(fake)()
