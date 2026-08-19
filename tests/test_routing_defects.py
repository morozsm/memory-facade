"""Regression tests for the three routing/commit defects found in production.

1. default_fetcher fed raw HTML to the router, so GitHub's inline CSS
   (``--tab-size-preference``) scored as a personal "preference" and the
   5000-char cap cut the page before any real content.
2. The router allowlist was hardcoded to global-user + infra, so taxonomy banks
   such as ``projects`` were rejected as explicit targets.
3. memory_reroute(commit=True) wired in a NoopRelocator and reported
   ``{"moved": ...}`` without touching any bank.
"""
from __future__ import annotations

import pytest

from mf import _route
from mf.ingest import strip_markup
from mf.reroute import Misroute, NoopRelocator, reroute_scan


GITHUB_HEAD = (
    "<html><head><title>GitHub - volcengine/OpenViking</title>"
    "<style>:root { --tab-size-preference: 4; } pre, code "
    "{ tab-size: var(--tab-size-preference); }</style>"
    "<script>window.x = {'locale':'en','prefer':1}</script></head>"
    "<body><p>OpenViking ships a docker compose deployment and an mcp server.</p>"
    "</body></html>"
)


class TestMarkupStripping:
    def test_style_and_script_bodies_are_dropped(self):
        text = strip_markup(GITHUB_HEAD)
        assert "tab-size-preference" not in text
        assert "window.x" not in text
        assert "OpenViking ships a docker compose deployment" in text

    def test_css_no_longer_scores_as_a_personal_preference(self):
        """The exact production misroute: CSS must not win the bank."""
        text = strip_markup(GITHUB_HEAD)
        route = _route.route(text)
        assert route.bank == "infra"

    def test_visible_text_survives_the_length_cap(self):
        """Body text must reach the router even when markup is huge."""
        padding = "<script>" + ("x" * 20000) + "</script>"
        text = strip_markup(padding + GITHUB_HEAD, limit=5000)
        assert "docker compose deployment" in text


class TestTaxonomyAllowlist:
    def test_projects_is_a_legal_explicit_target(self):
        route = _route.route("some project note", explicit_bank="projects")
        assert route.bank == "projects"

    def test_taxonomy_banks_are_allowed(self):
        for bank in ("projects", "business", "work", "medical", "product-rigplane"):
            assert bank in _route.BANK_ALLOWLIST

    def test_unknown_bank_is_still_rejected(self):
        with pytest.raises(_route.AmbiguousRouteError):
            _route.route("text", explicit_bank="not-a-bank")

    def test_personal_preference_still_routes_to_global_user(self):
        route = _route.route("I prefer concise answers; my working style is direct")
        assert route.bank == "global-user"


class TestRerouteCommitHonesty:
    rows = [{"id": "m1", "text": "haproxy and docker compose deployment on the orange pi"}]

    def test_dry_run_reports_proposals_without_applying(self):
        res = reroute_scan("global-user", self.rows, client=None, commit=False)
        assert res["misrouted"] == 1
        assert res["applied"] == []
        assert res["committed"] is False

    def test_commit_without_a_real_relocator_refuses_instead_of_lying(self):
        """A no-op must never be reported as a completed move."""
        with pytest.raises(NotImplementedError):
            reroute_scan("global-user", self.rows, client=None, commit=True)

    def test_noop_relocator_is_explicitly_marked_dry_run(self):
        applied = NoopRelocator().relocate(
            Misroute(id="m1", text="t", current_bank="global-user", target_bank="infra"),
            client=None,
        )
        assert applied["moved"] is False
        assert applied["dry_run"] is True

    def test_commit_with_a_real_relocator_applies(self):
        class Relocator:
            def __init__(self):
                self.calls = []

            def relocate(self, misroute, client):
                self.calls.append(misroute.id)
                return {"moved": True, "id": misroute.id, "to": misroute.target_bank}

        relo = Relocator()
        res = reroute_scan("global-user", self.rows, client=None, commit=True, relocator=relo)
        assert relo.calls == ["m1"]
        assert res["applied"][0]["moved"] is True
