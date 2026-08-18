"""Memory-Facade MCP server (stdio).

Registers curated tools. `mf.ping` is the connectivity smoke tool: it reports
Hindsight health. Real curation tools (recall, ingest_url, ...) are added in
later groups. The client is injectable for tests.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mf import config
from mf.dedupe import NoopConsolidator, DupRow, dedupe_scan
from mf.hindsight import HindsightClient
from mf.ingest import NoopCardWriter, ingest_url
from mf.recall import Synthesizer, recall
from mf.reroute import NoopRelocator, reroute_scan
from mf.session_docs import NoopDocWriter, session_to_docs

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


@mcp.tool()
def memory_recall(
    query: str,
    banks: list[str] | None = None,
    budget: str = "mid",
    max_items: int = 8,
) -> dict[str, Any]:
    """Curated semantic recall across Hindsight banks.

    Queries the given ``banks`` (default ``["global-user"]``), merges results
    with [[bank:id]] provenance, de-duplicates rows sharing a chunk, and returns
    a synthesis with citations. Read-only; never mutates memory.
    """
    client = _client()
    used_banks = banks or ["global-user"]
    result = recall(client, query=query, banks=used_banks, budget=budget)
    synth = Synthesizer()
    return {
        "query": query,
        "banks": used_banks,
        "recalled": len(result.items),
        "deduped": len(result.deduped_items()),
        "synthesis": synth.synthesize(result, limit=max_items),
        "items": [
            {
                "bank": it.bank,
                "id": it.id,
                "text": it.text,
                "type": it.fact_type,
                "tags": it.tags,
                "citation": it.citation,
            }
            for it in result.deduped_items()[:max_items]
        ],
    }


@mcp.tool()
def memory_ingest_url(
    url: str,
    explicit_bank: str | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    """Analyze a URL and produce a compact, cross-linked article card.

    Fetches the URL, auto-routes bank/tags, builds an article, auto-links to
    related existing cards, and (with ``commit=True``) persists card facts.
    Read-only by default.
    """
    client = _client()
    result = ingest_url(
        url,
        client,
        explicit_bank=explicit_bank,
        writer=NoopCardWriter() if commit else None,
        commit=commit,
    )
    article = result.article
    return {
        "url": url,
        "bank": article.bank,
        "title": article.title,
        "tags": article.tags,
        "related": result.related,
        "committed": result.committed,
        "summary": article.summary,
    }


@mcp.tool()
def memory_session_to_docs(
    facts: list[str],
    commit: bool = False,
) -> dict[str, Any]:
    """Turn a session's durable facts into a linked documentation set.

    Groups the facts into topic clusters, builds one Article per cluster, and
    cross-links them into a doc set. With ``commit=True`` the cards are
    persisted. Read-only by default.
    """
    client = _client()
    docs = session_to_docs(
        facts,
        client,
        writer=NoopDocWriter() if commit else None,
        commit=commit,
    )
    return {
        "committed": docs.committed,
        "articles": [
            {
                "title": a.title,
                "bank": a.bank,
                "tags": a.tags,
                "links": a.links,
                "summary": a.summary,
            }
            for a in docs.articles
        ],
    }


@mcp.tool()
def memory_dedupe(
    bank: str = "infra",
    sample_limit: int = 500,
    commit: bool = False,
) -> dict[str, Any]:
    """Find duplicate / over-fragmented memories in a bank and propose merging.

    Detects exact chunk_id collisions and normalized-text duplicates, returns
    the proposed groups. With ``commit=True`` runs consolidation (destructive);
    read-only by default.
    """
    client = _client()
    import urllib.parse

    encoded = urllib.parse.quote(bank, safe="")
    payload = client.get(f"/v1/default/banks/{encoded}/memories/list?limit={sample_limit}")
    items = payload.get("items", []) if isinstance(payload, dict) else []
    rows = [
        DupRow(
            id=str(it.get("id") or ""),
            text=str(it.get("text") or ""),
            chunk_id=it.get("chunk_id"),
        )
        for it in items
        if it.get("text")
    ]
    result = dedupe_scan(
        rows,
        client,
        consolidator=NoopConsolidator() if commit else None,
        commit=commit,
    )
    return result


@mcp.tool()
def memory_reroute(
    source_bank: str = "global-user",
    sample_limit: int = 500,
    commit: bool = False,
) -> dict[str, Any]:
    """Find memories misrouted to the wrong bank and propose relocating them.

    Detects rows in ``source_bank`` that deterministically belong in another
    bank (e.g. infra content in ``global-user``) and returns the move proposals.
    With ``commit=True`` relocates (destructive); read-only by default.
    """
    client = _client()
    import urllib.parse

    encoded = urllib.parse.quote(source_bank, safe="")
    payload = client.get(f"/v1/default/banks/{encoded}/memories/list?limit={sample_limit}")
    items = payload.get("items", []) if isinstance(payload, dict) else []
    result = reroute_scan(
        source_bank,
        items,
        client,
        relocator=NoopRelocator() if commit else None,
        commit=commit,
    )
    return result


def main(args: list[str] | None = None) -> None:
    """Run the MCP server.

    Transport defaults to stdio (for the LiteLLM runtime / local clients).
    Pass ``--transport sse`` (or ``http``) + ``--port`` to expose as a
    standalone HTTP/SSE server so remote MCP clients (e.g. Hermes over ``url``)
    can connect without the Orange Pi runtime.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="memory-facade")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http", "streamable-http"],
        default="stdio",
        help="MCP transport (default stdio).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8500, help="Listen port for HTTP/SSE.")
    parsed = parser.parse_args(args)
    # stdio has no bind address: FastMCP dispatches to run_stdio_async(), which
    # rejects host/port. Passing them raises TypeError on every connection and
    # the client sees nothing but "Connection closed".
    transport_kwargs: dict[str, object] = {}
    if parsed.transport != "stdio":
        transport_kwargs["host"] = parsed.host
        transport_kwargs["port"] = parsed.port
    mcp.run(transport=parsed.transport, **transport_kwargs)


if __name__ == "__main__":
    main()
