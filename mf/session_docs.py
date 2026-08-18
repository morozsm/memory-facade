"""mf.session_to_docs — turn a session's durable facts into a linked doc set.

The user's ask: "create a group of articles based on the current session, and
have it produce documentation."

Pipeline:
  1. split(facts)     -> topic clusters (deterministic keyword grouping, LLM
                          uplifts later behind a TopicSplitter interface)
  2. for each cluster -> build an Article card (title/summary from facts)
  3. link the group   -> every article links to the others (a doc set)
  4. route each       -> auto bank/tags per cluster

Deterministic-first, matching the project philosophy. With ``commit=False``
nothing is written.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from mf import _route
from mf.article import Article
from mf.hindsight import HindsightClient


# --- interfaces -------------------------------------------------------------------

class TopicSplitter(Protocol):
    """Groups fact strings into topic clusters -> list[(title, [facts])]."""

    def __call__(self, facts: list[str]) -> list[tuple[str, list[str]]]: ...


class DocWriter(Protocol):
    def write(self, article: Article, client: HindsightClient) -> Any: ...


# --- defaults ---------------------------------------------------------------------

def default_splitter(facts: list[str]) -> list[tuple[str, list[str]]]:
    """Deterministic clustering: group facts by routed bank + primary tag.

    Facts that route to the same (bank, first-tag) form one cluster; the cluster
    title is the routed bank name. Unroutable facts fall into a "general" bucket.
    """
    buckets: dict[tuple[str, str], list[str]] = {}
    for fact in facts:
        try:
            r = _route.route(fact)
            key = (r.bank, r.tags[0] if r.tags else "general")
        except _route.AmbiguousRouteError:
            key = ("general", "general")
        buckets.setdefault(key, []).append(fact)
    return [(f"{bank}/{tag}", items) for (bank, tag), items in buckets.items()]


class NoopDocWriter:
    def __init__(self) -> None:
        self.written: list[Article] = []

    def write(self, article: Article, client: HindsightClient) -> list[dict]:
        self.written.append(article)
        return article.to_hindsight_facts()


# --- results ----------------------------------------------------------------------

@dataclass
class DocSet:
    articles: list[Article] = field(default_factory=list)
    committed: bool = False

    def link_group(self) -> None:
        ids = [a.id or a.title for a in self.articles]
        for a in self.articles:
            mine = a.id or a.title
            for other in ids:
                if other != mine:
                    a.add_link(other)


# --- orchestration ----------------------------------------------------------------

def session_to_docs(
    facts: list[str],
    client: HindsightClient,
    *,
    splitter: Callable[[list[str]], list[tuple[str, list[str]]]] = default_splitter,
    writer: DocWriter | None = None,
    commit: bool = False,
) -> DocSet:
    """Produce a linked documentation set from a session's durable facts."""
    topics = splitter(facts)
    docs = DocSet(committed=commit)

    for title, cluster_facts in topics:
        combined = " ".join(cluster_facts)
        summary = (title + ": ") + combined[:300]
        try:
            r = _route.route(combined)
            bank = r.bank
            tags = r.tags
        except _route.AmbiguousRouteError:
            bank = "infra"  # degenerate fallback; caller can override
            tags = []
        article = Article(
            title=title,
            summary=summary,
            bank=bank,
            tags=tags,
            provenance={"session_facts": len(cluster_facts)},
        )
        article.validate()
        docs.articles.append(article)

    docs.link_group()

    if commit:
        writer_impl = writer or NoopDocWriter()
        for article in docs.articles:
            writer_impl.write(article, client)

    return docs
