"""mf.ingest_url — turn a URL into a compact, cross-linked article.

Pipeline (the user's headline ask: give a URL, get an analyzed, linked article):

  1. fetch(url)        -> readable text
  2. route(text)       -> auto bank + tags (mf._route)
  3. build Article     -> title/summary from content
  4. find_related()    -> auto-link to existing article cards in the bank
  5. store()           -> (LightRAG body) + Hindsight card facts

Everything external (HTML fetch, LightRAG body store, Hindsight write) is behind
an interface so ingest is testable and deployable incrementally. All side effects
can be dry-run: with ``commit=False`` nothing is written.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from mf import _route
from mf.article import Article
from mf.hindsight import HindsightClient


# --- external-interface Protocols -------------------------------------------------

class Fetcher(Protocol):
    """Fetches a URL and returns (title, readable_text)."""

    def __call__(self, url: str) -> tuple[str | None, str]: ...


class RelatedFinder(Protocol):
    """Finds existing article ids related to a given article."""

    def __call__(self, article: Article, client: HindsightClient, bank: str) -> list[str]: ...


class CardWriter(Protocol):
    """Persists an article card (Hindsight facts). No-op in dry-run."""

    def write(self, article: Article, client: HindsightClient) -> Any: ...


# --- default implementations ------------------------------------------------------

def strip_markup(raw: str, limit: int = 5000) -> str:
    """Reduce an HTML document to visible text, then cap it.

    Script and style bodies are removed before the tags, because their contents
    are not visible text and poison keyword routing: GitHub's inline CSS carries
    ``--tab-size-preference``, which the router scored as a personal
    "preference". Capping after stripping (rather than slicing the raw HTML)
    keeps real page content inside the budget instead of spending it on markup.
    """
    import html as htmlmod
    import re

    text = re.sub(
        r"<(script|style|noscript|template)\b[^>]*>.*?</\1\s*>",
        " ",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmlmod.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:limit]


def default_fetcher(url: str) -> tuple[str | None, str]:
    """Minimal HTTP fetch. Lightweight, no external libs; best-effort text."""
    from urllib.parse import urlparse
    from urllib.request import urlopen

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme: {parsed.scheme}")
    with urlopen(url, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    import html as htmlmod
    import re

    title = None
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    if m:
        title = htmlmod.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
    return title, strip_markup(raw)


class DefaultLinkFinder:
    """Link by shared tags + semantic recall of article-cards in the bank."""

    def __call__(self, article: Article, client: HindsightClient, bank: str) -> list[str]:
        payload = client.recall(bank, query=article.summary, budget="low", max_tokens=600)
        results = payload.get("results", []) if isinstance(payload, dict) else []
        out: list[str] = []
        for r in results:
            tags = r.get("tags") or []
            if len(set(tags) & set(article.tags)) >= 1:
                rid = str(r.get("id") or "")
                if rid and rid != article.id:
                    out.append(rid)
        return out[:5]


class NoopCardWriter:
    """Dry-run writer: records the article, writes nothing."""

    def __init__(self) -> None:
        self.written: list[Article] = []

    def write(self, article: Article, client: HindsightClient) -> list[dict]:
        self.written.append(article)
        return article.to_hindsight_facts()


# --- orchestration -----------------------------------------------------------------

@dataclass
class IngestResult:
    article: Article
    related: list[str] = field(default_factory=list)
    committed: bool = False
    bank: str = ""


def ingest_url(
    url: str,
    client: HindsightClient,
    *,
    fetcher: Fetcher = default_fetcher,
    finder: RelatedFinder | None = None,
    writer: CardWriter | None = None,
    explicit_bank: str | None = None,
    commit: bool = False,
) -> IngestResult:
    """Analyze a URL and produce a linked article card.

    With ``commit=False`` (default) nothing is written to Hindsight/LightRAG;
    the pipeline returns the prepared article and its proposed links.
    """
    title, text = fetcher(url)
    if not text.strip():
        raise ValueError(f"no readable content from {url}")

    route = _route.route(
        f"{title or ''} {text}", explicit_bank=explicit_bank
    )
    summary = (title or "Imported article") + ": " + (text[:300])
    article = Article(
        title=title or "Imported article",
        summary=summary,
        bank=route.bank,
        tags=route.tags,
        source_url=url,
        provenance={"source_url": url},
    )
    article.validate()

    finder_impl = finder or DefaultLinkFinder()
    related = finder_impl(article, client, article.bank)
    for rid in related:
        article.add_link(rid)

    facts: list[dict] = []
    if commit:
        writer_impl = writer or NoopCardWriter()
        facts = writer_impl.write(article, client)

    return IngestResult(
        article=article,
        related=related,
        committed=commit,
        bank=article.bank,
    )
