"""Tests for mf.session_docs — session -> linked doc set (no network)."""

from mf.session_docs import DocSet, default_splitter, session_to_docs


class FakeClient:
    def __init__(self):
        self.called = False

    def recall(self, *a, **kw):
        self.called = True
        return {"results": []}


class _Writer:
    def __init__(self):
        self.written = []

    def write(self, article, client):
        self.written.append(article)
        return article.to_hindsight_facts()


def test_session_to_docs_builds_linked_docset():
    client = FakeClient()
    facts = [
        "orange pi redis redeploy via docker compose",
        "litellm gateway configured with digitalocean",
        "I prefer concise status updates",
    ]
    docs = session_to_docs(facts, client)
    assert isinstance(docs, DocSet)
    assert len(docs.articles) >= 1
    # group is fully cross-linked
    for a in docs.articles:
        others = [b.title for b in docs.articles if b is not a]
        for other in others:
            assert other in a.links or a.id in a.links
    assert not docs.committed  # dry-run by default


def test_session_to_docs_commit_writes_all():
    client = FakeClient()
    writer = _Writer()
    docs = session_to_docs(
        ["deploy ansible semaphore on orange pi"],
        client,
        writer=writer,
        commit=True,
    )
    assert docs.committed is True
    assert len(writer.written) == len(docs.articles)
    assert all(w.bank == "infra" for w in writer.written)


def test_default_splitter_groups_by_domain():
    facts = [
        "deploy redis infra orange pi",
        "litellm gateway infra mcp",
        "I prefer direct action",
    ]
    topics = default_splitter(facts)
    # infra-ish facts cluster together; personal has its own topic
    titles = [t for t, _ in topics]
    assert len(titles) >= 2
    infra_topic = next(t for t in titles if "infra" in t)


def test_docset_empty():
    client = FakeClient()
    docs = session_to_docs([], client)
    assert docs.articles == []
