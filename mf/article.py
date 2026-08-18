"""Article-card model for Memory-Facade.

An ``Article`` is the compact, human-readable "card" that curation produces:

  - body  -> stored in LightRAG (large corpus), referenced by ``body_pointer``
  - card  -> stored in Hindsight as durable facts (title, summary, links,
             provenance, pointer). Per the Common Memory contract (§1.6),
             Hindsight holds decisions/summaries/pointers, never the corpus.

``links`` are bidirectional references to other article ids, giving the
wiki-like cross-linking the user asked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Article:
    title: str
    summary: str
    bank: str
    tags: list[str] = field(default_factory=list)
    source_url: str | None = None
    body_pointer: str | None = None  # LightRAG document id for the full body
    links: list[str] = field(default_factory=list)  # related Article ids
    id: str | None = None
    provenance: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("Article title is required")
        if not self.summary.strip():
            raise ValueError("Article summary is required")
        if not self.bank:
            raise ValueError("Article bank is required")

    def add_link(self, other_id: str) -> bool:
        """Add a cross-link if not present; returns True if added."""
        if other_id and other_id != self.id and other_id not in self.links:
            self.links.append(other_id)
            return True
        return False

    def to_hindsight_facts(self) -> list[dict]:
        """Emit the durable Hindsight facts for this card.

        Each fact is a short, self-contained durable statement with provenance
        metadata, safe for the bank's retention policy.
        """
        provenance = {
            "source": "memory-facade",
            "agent": "memory-facade",
            "record_type": "article-card",
            "contains_secrets": False,
        }
        provenance.update(self.provenance)
        facts = [
            {
                "text": (
                    f"Article '{self.title}': {self.summary} "
                    f"(links: {', '.join(self.links) or 'none'})"
                ),
                "tags": list(self.tags),
                "metadata": {
                    **provenance,
                    "article_id": self.id or self.title,
                    "body_pointer": self.body_pointer,
                },
            }
        ]
        return facts
