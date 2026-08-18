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
from mf.ingest import NoopCardWriter, ingest_url
from mf.recall import Synthesizer, recall
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
