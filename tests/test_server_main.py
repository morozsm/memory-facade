"""Transport wiring for the `memory-facade` entrypoint.

The stdio transport is what the LiteLLM runtime uses, and FastMCP's
``run_stdio_async()`` takes no bind address: forwarding ``host``/``port``
unconditionally raises ``TypeError`` on every connection, so the server is
reachable only under HTTP. These tests pin which kwargs reach ``mcp.run``.
"""

from __future__ import annotations

from typing import Any

import pytest

from mf import server


@pytest.fixture()
def captured_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_run(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(server.mcp, "run", fake_run)
    return captured


def test_stdio_is_the_default_and_carries_no_bind_address(captured_run: dict[str, Any]) -> None:
    server.main([])

    assert captured_run == {"transport": "stdio"}


def test_explicit_stdio_carries_no_bind_address(captured_run: dict[str, Any]) -> None:
    server.main(["--transport", "stdio", "--host", "0.0.0.0", "--port", "9000"])

    assert captured_run == {"transport": "stdio"}


@pytest.mark.parametrize("transport", ["sse", "http", "streamable-http"])
def test_network_transports_carry_the_bind_address(
    captured_run: dict[str, Any], transport: str
) -> None:
    server.main(["--transport", transport, "--host", "0.0.0.0", "--port", "9000"])

    assert captured_run == {"transport": transport, "host": "0.0.0.0", "port": 9000}
