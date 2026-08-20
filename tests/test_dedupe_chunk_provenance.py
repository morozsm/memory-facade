"""Regression test: chunk_id collisions are not duplicates.

Measured on the live global-user bank (7004 facts): grouping by chunk_id yields
846 groups covering 4531 rows (64.7% of the bank), yet 0 of those groups hold
identical text and 843 hold genuinely distinct facts. Hindsight extracts many
separate facts from one source chunk, so a shared chunk_id means shared
provenance, not redundancy. Consolidating on it would destroy real memory.
"""

from mf.dedupe import DupRow, find_duplicates


def test_same_chunk_different_facts_is_not_a_duplicate():
    """Distinct facts extracted from one chunk must not be grouped."""
    rows = [
        DupRow(id="a", text="The parser accepts ISO-8601 timestamps.", chunk_id="c_17"),
        DupRow(id="b", text="Retries use exponential backoff capped at 30s.", chunk_id="c_17"),
        DupRow(id="c", text="The CLI reads its config from XDG_CONFIG_HOME.", chunk_id="c_17"),
    ]

    groups = find_duplicates(rows)

    assert groups == [], (
        "facts sharing a chunk_id but differing in text were grouped as duplicates; "
        "shared chunk_id means shared provenance, not redundancy"
    )


def test_identical_text_is_still_a_duplicate():
    """True redundancy must still be detected, regardless of chunk."""
    rows = [
        DupRow(id="a", text="A vector database stores embeddings for retrieval.", chunk_id="c_1"),
        DupRow(id="b", text="A vector database stores embeddings for retrieval.", chunk_id="c_9"),
    ]

    groups = find_duplicates(rows)

    assert len(groups) == 1
    assert len(groups[0].duplicates) == 1


def test_identical_text_within_one_chunk_is_a_duplicate():
    """A chunk that really does repeat a fact is still redundancy."""
    rows = [
        DupRow(id="a", text="The scheduler adds a dispatch guard.", chunk_id="c_4"),
        DupRow(id="b", text="The scheduler adds a dispatch guard.", chunk_id="c_4"),
        DupRow(id="c", text="The driver introduces runtime contracts.", chunk_id="c_4"),
    ]

    groups = find_duplicates(rows)

    assert len(groups) == 1, "only the repeated fact should form a group"
    assert len(groups[0].duplicates) == 1
    assert {groups[0].canonical.id, groups[0].duplicates[0].id} == {"a", "b"}


def test_canonical_is_earliest_and_order_is_preserved():
    """Grouping is order-stable: the canonical row is the first occurrence,
    groups follow first appearance, and three-plus copies collapse into one
    group rather than a chain of pairs.
    """
    rows = [
        DupRow(id="1", text="alpha", chunk_id="c_1"),
        DupRow(id="2", text="beta", chunk_id="c_2"),
        DupRow(id="3", text="ALPHA", chunk_id="c_3"),
        DupRow(id="4", text="gamma", chunk_id="c_4"),
        DupRow(id="5", text="  alpha  ", chunk_id="c_5"),
        DupRow(id="6", text="beta", chunk_id="c_6"),
    ]

    groups = find_duplicates(rows)

    assert [g.canonical.id for g in groups] == ["1", "2"]
    assert [d.id for d in groups[0].duplicates] == ["3", "5"]
    assert [d.id for d in groups[1].duplicates] == ["6"]
