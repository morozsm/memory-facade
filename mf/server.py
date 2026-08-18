"""Memory-Facade MCP server (stdio).

Registers curated tools. `mf.ping` is the connectivity smoke tool: it reports
Hindsight health. Real curation tools (recall, ingest_url, ...) are added in
later groups. The client is injectable for tests.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mf import config
from mf.hindsight import HindsightClient

mcp = FastMCP("memory-facade")


def _client() -> HindsightClient:
    return HindsightClient(
        api_url=config.hindsight_api_url(),
        api_key=config.hindsight_api_key(),
        timeout=config.hindsight_timeout(),
    )


def make_ping(_client: HindsightClient | None = None):
    """Return a ping callable bound to an optional injected client."""

    def ping() -> dict[str, Any]:
        client = _client or HindsightClient(
            api_url=config.hindsight_api_url(),
            api_key=config.hindsight_api_key(),
            timeout=config.hindsight_timeout(),
        )
        health = client.health()
        return {
            "status": health.get("status"),
            "database": health.get("database"),
            "api_url": config.hindsight_api_url(),
        }

    return ping


@mcp.tool()
def ping() -> dict[str, Any]:
    """Report Hindsight connectivity/health from the facade."""
    return make_ping()()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
