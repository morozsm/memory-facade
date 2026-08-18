"""Tests for mf.ingest — URL -> linked article pipeline (no network)."""

from mf.article import Article
from mf.ingest import IngestResult, ingest_url


class FakeClient:
    """Scripted recall for the link finder."""

    def __init__(self, results=None):
        self.results = results or {}
        self.recall_calls = []

    def recall(self, bank, query, types=None, budget="mid", **kw):
        self.recall_calls.append((bank, query))
        return {"results": self.results.get(bank, [])}


def _fake_fetcher(url):
    return ("Redis status", "redis is extracted separately and not yet deployed to production")


class _Finder:
    def __call__(self, article, client, bank):
        return ["article-777"]


class _Writer:
    def __init__(self):
        self.written = []

    def write(self, article, client):
        self.written.append(article)
        return article.to_hindsight_facts()


def test_ingest_routes_and_builds_article():
    client = FakeClient()
    res = ingest_url("https://x.dev/redis", client, fetcher=_fake_fetcher)
    assert isinstance(res, IngestResult)
    assert res.article.bank == "infra"
    assert res.article.title == "Redis status"
    assert res.article.source_url == "https://x.dev/redis"
    assert not res.committed  # default is read-only


def test_ingest_auto_links_related():
    client = FakeClient()
    res = ingest_url("https://x.dev/redis", client, fetcher=_fake_fetcher, finder=_Finder())
    assert res.related == ["article-777"]
    assert "article-777" in res.article.links


def test_ingest_commit_writes_card():
    client = FakeClient()
    writer = _Writer()
    res = ingest_url(
        "https://x.dev/redis",
        client,
        fetcher=_fake_fetcher,
        writer=writer,
        commit=True,
    )
    assert res.committed is True
    assert len(writer.written) == 1
    assert writer.written[0].bank == "infra"


def test_ingest_explicit_bank_override():
    client = FakeClient()
    res = ingest_url(
        "https://x.dev/personal", client, fetcher=_fake_fetcher, explicit_bank="global-user"
    )
    assert res.article.bank == "global-user"


def test_ingest_empty_content_raises():
    client = FakeClient()

    def empty(url):
        return ("", "   ")

    try:
        ingest_url("https://x.dev/empty", client, fetcher=empty)
        assert False, "expected ValueError"
    except ValueError:
        pass
