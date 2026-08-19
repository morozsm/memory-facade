"""mf.reroute — find misrouted memories and propose relocating them.

Baseline (2026-08-18): `global-user` carries ~38.6% infra-themed and ~85%
Cyrillic working-transcript content, despite the bank's mission being personal,
durable preferences only. This tool surfaces rows that deterministically route
to a different bank and proposes the move.

Detection: for each row in ``source_bank``, run ``_route.route``; if it
confidently resolves to a bank != ``source_bank``, flag a misroute proposal.

``commit=True`` performs relocation through a ``Relocator``. Default is a no-op
(records proposals); the real re-retain + invalidate against Hindsight is wired
in Group 4 — it is the destructive step and this repo requires explicit
approval before write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from mf import _route


@dataclass
class Misroute:
    id: str
    text: str
    current_bank: str
    target_bank: str
    method: str = "auto"


class Relocator(Protocol):
    """Moves a memory to another bank (mutating). No-op by default."""

    def relocate(self, misroute: Misroute, client: Any) -> dict[str, Any]: ...


class NoopRelocator:
    """Records proposals without moving anything.

    ``relocate`` reports ``moved: False`` and ``dry_run: True`` so a no-op can
    never be mistaken for a completed move in the tool output.
    """

    def __init__(self) -> None:
        self.proposals: list[Misroute] = []

    def relocate(self, misroute: Misroute, client: Any) -> dict[str, Any]:
        self.proposals.append(misroute)
        return {
            "moved": False,
            "dry_run": True,
            "id": misroute.id,
            "to": misroute.target_bank,
        }


def find_misroutes(
    source_bank: str,
    rows: list[dict],
    allow_targets: tuple[str, ...] = ("infra", "global-user"),
) -> list[Misroute]:
    """Rows that deterministically route to a bank other than ``source_bank``."""
    out: list[Misroute] = []
    for it in rows:
        text = str(it.get("text") or "").strip()
        if not text:
            continue
        memo_id = str(it.get("id") or "")
        try:
            r = _route.route(text, bank_allowlist=allow_targets)
        except _route.AmbiguousRouteError:
            continue  # don't guess
        if r.bank != source_bank:
            out.append(
                Misroute(
                    id=memo_id,
                    text=text,
                    current_bank=source_bank,
                    target_bank=r.bank,
                    method=r.method,
                )
            )
    return out


def reroute_scan(
    source_bank: str,
    rows: list[dict],
    client: Any,
    *,
    allow_targets: tuple[str, ...] = _route.BANK_ALLOWLIST,
    relocator: Relocator | None = None,
    commit: bool = False,
) -> dict[str, Any]:
    """Analyze misrouted rows. If ``commit``, relocate each.

    ``commit=True`` requires a relocator that actually moves memories. Without
    one the call raises instead of returning a success-shaped no-op: reporting a
    move that never happened is worse than refusing to move.
    """
    misroutes = find_misroutes(source_bank, rows, allow_targets=allow_targets)
    if commit and relocator is None:
        raise NotImplementedError(
            "commit=True needs a relocator that actually moves facts. Hindsight's "
            "only move primitive is document-level (/document-transfer, export ZIP "
            "-> import), while these proposals are per fact: sampled global-user "
            "documents hold ~74 facts each (max 320) and 2 of 5 mix facts belonging "
            "to different banks, so transferring a document would drag unrelated "
            "facts along. Re-run with commit=False for the proposals, or re-retain "
            "the individual facts into the target bank and invalidate the originals."
        )
    relo = relocator or NoopRelocator()
    applied: list[dict[str, Any]] = []
    if commit and misroutes:
        for m in misroutes:
            applied.append(relo.relocate(m, client))
    return {
        "source_bank": source_bank,
        "rows_scanned": len(rows),
        "misrouted": len(misroutes),
        "committed": commit,
        "proposals": [
            {"id": m.id, "target_bank": m.target_bank, "method": m.method}
            for m in misroutes
        ],
        "applied": applied,
    }
