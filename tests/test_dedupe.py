"""Tests for mf.dedupe — duplicate detection & consolidation (no network)."""

from mf.dedupe import DupRow, NoopConsolidator, dedupe_scan, find_duplicates


def _row(id_, text, chunk=None):
    return DupRow(id=id_, text=text, chunk_id=chunk)


def test_same_chunk_different_text_is_not_a_duplicate():
    """Shared chunk_id is shared provenance, not redundancy.

    Hindsight extracts many distinct facts from one source chunk, so grouping
    on chunk_id alone would propose merging unrelated memories.
    """
    rows = [
        _row("1", "fact a", chunk="c9"),
        _row("2", "fact a duplicate", chunk="c9"),
    ]
    assert find_duplicates(rows) == []


def test_repeated_text_in_one_chunk_detected():
    rows = [
        _row("1", "fact a", chunk="c9"),
        _row("2", "fact a", chunk="c9"),
    ]
    groups = find_duplicates(rows)
    assert len(groups) == 1
    assert groups[0].canonical.id == "1"
    assert groups[0].duplicates[0].id == "2"


def test_normalized_text_duplicate_detected():
    rows = [
        _row("1", "Redis is not deployed"),
        _row("2", "redis is   not  DEPLOYED"),  # same normalized text, diff chunk
    ]
    groups = find_duplicates(rows)
    assert any(g.canonical.id == "1" and g.duplicates[0].id == "2" for g in groups)


def test_no_duplicates():
    rows = [_row("1", "alpha fact", "c1"), _row("2", "beta fact", "c2")]
    assert find_duplicates(rows) == []


def test_dedupe_scan_dry_run_no_commit():
    client = object()
    rows = [
        _row("1", "fact", "c9"),
        _row("2", "fact", "c9"),
    ]
    result = dedupe_scan(rows, client)
    assert result["duplicate_groups"] == 1
    assert result["committed"] is False
    assert result["applied"] == []


def test_dedupe_scan_commit_applies():
    client = object()
    cons = NoopConsolidator()
    rows = [
        _row("1", "fact", "c9"),
        _row("2", "fact", "c9"),
    ]
    result = dedupe_scan(rows, client, consolidator=cons, commit=True)
    assert result["committed"] is True
    assert len(cons.groups) == 1
    assert result["applied"][0]["merged"] == 2
