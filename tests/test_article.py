"""Tests for mf.article — article-card model (no network)."""

import pytest

from mf.article import Article


def _article(**kw):
    defaults = {
        "title": "Redis deploy status",
        "summary": "Redis is extracted separately and not yet deployed.",
        "bank": "infra",
        "tags": ["domain:infra"],
    }
    defaults.update(kw)
    return Article(**defaults)


def test_article_requires_title_and_summary():
    with pytest.raises(ValueError):
        _article(title="").validate()
    with pytest.raises(ValueError):
        _article(summary="").validate()
    with pytest.raises(ValueError):
        _article(bank="").validate()


def test_article_add_link_dedup():
    a = _article(id="a")
    assert a.add_link("b") is True
    assert a.add_link("b") is False  # already present
    assert a.add_link("a") is False  # self-link rejected
    assert a.links == ["b"]


def test_to_hindsight_facts_has_provenance():
    a = _article(id="abc", body_pointer="lightrag-doc-1", source_url="https://x.dev/redis")
    facts = a.to_hindsight_facts()
    assert len(facts) == 1
    fact = facts[0]
    assert "Redis deploy status" in fact["text"]
    assert "article-card" in fact["metadata"]["record_type"]
    assert fact["metadata"]["contains_secrets"] is False
    assert fact["metadata"]["body_pointer"] == "lightrag-doc-1"
    assert fact["metadata"]["article_id"] == "abc"


def test_article_provenance_merge():
    a = _article(id="x", provenance={"repo_path": "/proj", "session_id": "s1"})
    fact = a.to_hindsight_facts()[0]
    assert fact["metadata"]["repo_path"] == "/proj"
    assert fact["metadata"]["session_id"] == "s1"
