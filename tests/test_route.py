"""Tests for mf._route — auto bank/tag routing (no network)."""

import pytest

from mf._route import AmbiguousRouteError, derive_tags, route


def test_routes_infra_text_to_infra():
    r = route("redployed redis through docker compose on orange pi")
    assert r.bank == "infra"
    assert r.method == "auto"


def test_routes_personal_preference_to_global_user():
    r = route("I prefer concise status updates and direct action")
    assert r.bank == "global-user"
    assert r.method == "auto"


def test_explicit_bank_override_wins():
    r = route("any text", explicit_bank="infra")
    assert r.bank == "infra"
    assert r.method == "explicit"


def test_explicit_bank_not_in_allowlist_raises():
    with pytest.raises(AmbiguousRouteError):
        route("text", explicit_bank="sensitive-new-bank")


def test_ambiguous_content_raises():
    # No keyword matches -> should ask, not guess
    with pytest.raises(AmbiguousRouteError):
        route("the weather today is quite pleasant in the park")


def test_derive_tags_memory_domain():
    tags = derive_tags("hindsight recall and retain memory policy")
    assert "domain:memory" in tags
    assert "project:common-memory" in tags


def test_derive_tags_infra_domain():
    tags = derive_tags("litellm gateway deploy via mcp")
    assert "service:ai-gateway" in tags
    assert "domain:infra" in tags
