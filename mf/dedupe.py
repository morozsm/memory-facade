"""mf.dedupe — find and propose consolidation of duplicate/over-fragmented rows.

Detection (deterministic, no LLM): normalized-text equality. The same statement
stored twice is redundancy and can be consolidated.

``chunk_id`` is NOT used. An earlier baseline (2026-08-18) read ~88% chunk-
colliding rows as duplicates; re-measuring the live global-user bank on
2026-08-19 disproved that: of 846 chunk groups covering 4531 of 7004 facts,
0 held identical text and 843 held genuinely distinct facts. Hindsight extracts
many facts from one source chunk, so a shared chunk_id is shared provenance and
consolidating on it destroys real memory.

``commit=True`` performs consolidation through a ``Consolidator``. The default
Consolidator is a no-op (records what WOULD be merged); the real Hindsight
invalidate/merge API is wired in Group 4 (deploy), since that is the destructive
step and this repo's policy is explicit-approval-before-write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class DupRow:
    id: str
    text: str
    chunk_id: str | None = None

    def normalized_text(self) -> str:
        return " ".join(self.text.lower().split())


@dataclass
class DupGroup:
    canonical: DupRow
    duplicates: list[DupRow] = field(default_factory=list)

    @property
    def members(self) -> list[DupRow]:
        return [self.canonical, *self.duplicates]


class Consolidator(Protocol):
    """Performs consolidation (mutating). No-op by default."""

    def consolidate(self, group: DupGroup, client: Any) -> dict[str, Any]: ...


class NoopConsolidator:
    """Dry-run: records groups, mutates nothing."""

    def __init__(self) -> None:
        self.groups: list[DupGroup] = []

    def consolidate(self, group: DupGroup, client: Any) -> dict[str, Any]:
        self.groups.append(group)
        return {"merged": len(group.members), "canonical": group.canonical.id}


def _lex_sim(a: str, b: str) -> bool:
    return a.normalized_text() == b.normalized_text()


def find_duplicates(rows: list[DupRow]) -> list[DupGroup]:
    """Group rows by normalized text equality. Deterministic.

    ``chunk_id`` is deliberately NOT a duplicate signal. Hindsight extracts many
    separate facts from a single source chunk, so a shared chunk_id records
    shared provenance, not redundancy. Measured on the live global-user bank
    (7004 facts): chunk grouping produced 846 groups covering 4531 rows (64.7%
    of the bank) while 0 groups held identical text and 843 held genuinely
    distinct facts — consolidating on it would have destroyed real memory.
    """
    groups: list[DupGroup] = []

    def add_group(members: list[DupRow]) -> None:
        if len(members) >= 2:
            groups.append(DupGroup(canonical=members[0], duplicates=members[1:]))

    used: set[str] = set()

    # Normalized-text duplicates: the same statement stored more than once,
    # whether or not the copies share a chunk.
    remaining = [r for r in rows if r.id not in used]
    while remaining:
        first = remaining[0]
        dupes = [r for r in remaining[1:] if _lex_sim(first, r)]
        # always consume the first row, whether or not it has duplicates
        ids = {first.id, *(r.id for r in dupes)}
        used |= ids
        if dupes:
            add_group([first, *dupes])
        remaining = [r for r in rows if r.id not in used]

    return groups


def dedupe_scan(
    rows: list[DupRow],
    client: Any,
    *,
    consolidator: Consolidator | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    """Analyze duplicates. If ``commit``, run consolidation per group."""
    groups = find_duplicates(rows)
    cons = consolidator or NoopConsolidator()
    applied: list[dict[str, Any]] = []
    if commit and groups:
        for group in groups:
            applied.append(cons.consolidate(group, client))
    return {
        "rows_scanned": len(rows),
        "duplicate_groups": len(groups),
        "rows_in_duplicates": sum(len(g.members) for g in groups),
        "committed": commit,
        "groups": [
            {
                "canonical": g.canonical.id,
                "duplicates": [d.id for d in g.duplicates],
                "text": g.canonical.text[:120],
            }
            for g in groups
        ],
        "applied": applied,
    }
