"""Tests for mf.reroute — misrouted-memory detection & relocation (no network)."""

from mf.reroute import NoopRelocator, find_misroutes, reroute_scan


def _row(id_, text):
    return {"id": id_, "text": text}


def test_detects_infra_fact_in_global_user():
    rows = [_row("1", "orange pi redis deploy via docker compose infra")]
    mis = find_misroutes("global-user", rows)
    assert len(mis) == 1
    assert mis[0].target_bank == "infra"
    assert mis[0].current_bank == "global-user"


def test_ignores_rows_already_in_correct_bank():
    rows = [_row("1", "I prefer direct action and concise status")]
    mis = find_misroutes("global-user", rows)
    assert mis == []  # personal routing stays in global-user


def test_ignores_ambiguous_rows():
    rows = [_row("1", "the weather today is nice in the park")]
    mis = find_misroutes("global-user", rows)
    assert mis == []


def test_scan_dry_run_no_commit():
    client = object()
    rows = [_row("1", "deploy ansible semaphore on orange pi")]
    result = reroute_scan("global-user", rows, client)
    assert result["misrouted"] == 1
    assert result["committed"] is False
    assert result["applied"] == []


def test_scan_commit_applies():
    client = object()
    relo = NoopRelocator()
    rows = [_row("1", "deploy redis infra on orange pi")]
    result = reroute_scan("global-user", rows, client, relocator=relo, commit=True)
    assert result["committed"] is True
    assert len(relo.proposals) == 1
    assert relo.proposals[0].target_bank == "infra"
