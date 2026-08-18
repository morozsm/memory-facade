"""mf.recall — curated semantic recall across one or more Hindsight banks.

Fetches semantic recall per bank, merges the results with explicit
bank-provenance labels, de-duplicates rows that share a chunk_id, and returns a
deterministic "curated" answer (top items + a short synthesis with citations).

LLM synthesis is pluggable behind ``Synthesizer``; the default implementation is
deterministic (concatenates top items with [[bank:id]] citations) so the tool is
useful with zero LLM cost. A real LLM synthesizer can be swapped in later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from mf.hindsight import HindsightClient

DEFAULT_BUDGET = "mid"
DEFAULT_TYPES = ("world", "experience", "observation")


@dataclass
class RecalledItem:
    bank: str
    id: str
    text: str
    fact_type: str | None = None
    tags: list[str] = field(default_factory=list)
    chunk_id: str | None = None
    score: float | None = None

    @property
    def citation(self) -> str:
        return f"[[{self.bank}:{self.id}]]"


@dataclass
class RecallResult:
    query: str
    items: list[RecalledItem]
    synthesizer_used: str

    def deduped_items(self) -> list[RecalledItem]:
        """Drop rows sharing the same (bank, chunk_id), preferring first hit."""
        seen: set[tuple[str, str]] = set()
        out: list[RecalledItem] = []
        for item in self.items:
            key = (item.bank, item.chunk_id or item.id)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out


class Synthesizer:
    """Deterministic default: build a readable summary with [[bank:id]] cites."""

    name = "deterministic"

    def synthesize(self, result: RecallResult, limit: int = 8) -> str:
        items = result.deduped_items()[:limit]
        lines = []
        for item in items:
            cite = f"{item.text.rstrip()} {item.citation}"
            lines.append(f"- [{item.bank}] {cite}")
        if not lines:
            return "No matching memories recalled."
        header = f"Recalled {len(items)} memories across {sorted({i.bank for i in items})}:"
        return "\n".join([header, *lines])


class RecallError(RuntimeError):
    pass


def _parse_recall_payload(payload: Any, bank: str) -> list[RecalledItem]:
    if not isinstance(payload, dict):
        raise RecallError(f"recall for {bank} returned non-object")
    items = payload.get("results")
    if not isinstance(items, list):
        raise RecallError(f"recall for {bank} has no 'results' list")
    out: list[RecalledItem] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        out.append(
            RecalledItem(
                bank=bank,
                id=str(raw.get("id") or ""),
                text=str(raw.get("text") or ""),
                fact_type=raw.get("type"),
                tags=list(raw.get("tags") or []),
                chunk_id=raw.get("chunk_id"),
            )
        )
    return out


def recall(
    client: HindsightClient,
    query: str,
    banks: Sequence[str] = ("global-user",),
    types: Iterable[str] = DEFAULT_TYPES,
    budget: str = DEFAULT_BUDGET,
    synthesizer: Synthesizer | None = None,
) -> RecallResult:
    """Recall across ``banks``, merge with provenance, and synthesize.

    ``client`` is injected so tests can pass a fake with a scripted ``recall``.
    """
    syn = synthesizer or Synthesizer()
    all_items: list[RecalledItem] = []
    for bank in banks:
        payload = client.recall(
            bank,
            query=query,
            types=list(types),
            budget=budget,
        )
        all_items.extend(_parse_recall_payload(payload, bank))

    result = RecallResult(query=query, items=all_items, synthesizer_used=syn.name)
    return result
