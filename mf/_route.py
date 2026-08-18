"""Auto bank/tag routing for Memory-Facade.

Resolves which Hindsight bank + deterministic tags a piece of content belongs
in, WITHOUT the caller having to remember static routing rules.

Strategy (deterministic-first, matching the project's "ask, don't guess"
safety rule):
  1. ``explicit_bank`` override wins if supplied.
  2. A keyword scorer maps content to one of the known banks.
  3. If the winning score is below ``ambiguity_threshold`` and no override was
     given, raise ``AmbiguousRouteError`` (the caller should ask the user,
     never silently invent or create a bank).

Only existing, taxonomy-approved banks may be targeted. ``BANK_ALLOWLIST`` is
the hard boundary; the facade never creates a bank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# Bank -> indicative keywords (lowercased). Keep in sync with
# ~/Projects/common-memory/docs/hindsight-bank-taxonomy.md.
DEFAULT_BANK_RULES: dict[str, list[str]] = {
    "global-user": [
        "preference", "prefer", "working style", "engineering value",
        "language preference", "memory policy", "i want", "i prefer",
        "cross-project", "personal",
    ],
    "infra": [
        "infra", "infrastructure", "deploy", "deployment", "redeploy",
        "ansible", "semaphore", "nginx", "haproxy", "tailscale", "docker",
        "compose", "orange pi", "orange-pi", "litellm", "gateway", "mcp",
        "bws", "vault", "redis", "postgres", "hindsight", "common-memory",
        "unifi", "udm", "home assistant", "hass", "ollama", "ha proxy",
    ],
}

# Tag prefixes we may emit deterministically. Values are derived from keywords.
TAG_KEYWORDS: dict[str, list[str]] = {
    "domain:memory": ["hindsight", "common-memory", "memory", "recall", "retain"],
    "domain:infra": ["infra", "infrastructure", "ansible", "deploy", "semaphore", "nginx", "haproxy", "unifi", "home assistant", "hass"],
    "project:common-memory": ["common-memory", "hindsight", "memory"],
    "service:ai-gateway": ["litellm", "gateway", "mcp", "ai-gateway"],
}

DEFAULT_AMBIGUITY_THRESHOLD = 1  # at least one keyword hit required to route


class AmbiguousRouteError(RuntimeError):
    def __init__(self, message: str = "") -> None:
        super().__init__(
            message
            or "Could not reliably determine target bank; ask the user instead of guessing."
        )


@dataclass
class Route:
    bank: str
    tags: list[str] = field(default_factory=list)
    method: str = "default"  # "explicit" | "auto" | "ambiguous"


def _hits(text: str, keywords: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if kw in lowered)


def derive_tags(text: str) -> list[str]:
    """Deterministically derive tags from keyword presence (dedup, ordered)."""
    lowered = text.lower()
    tags: list[str] = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            tags.append(tag)
    return tags


def route(
    text: str,
    bank_allowlist: Iterable[str] = ("global-user", "infra"),
    explicit_bank: str | None = None,
    ambiguity_threshold: int = DEFAULT_AMBIGUITY_THRESHOLD,
) -> Route:
    """Route ``text`` to a bank + tags.

    Raises ``AmbiguousRouteError`` when no reliable bank can be determined and
    the caller did not supply an override.
    """
    allow = list(bank_allowlist)

    if explicit_bank is not None:
        if explicit_bank not in allow:
            raise AmbiguousRouteError(
                f"explicit bank '{explicit_bank}' not in allowlist {allow}"
            )
        return Route(bank=explicit_bank, tags=derive_tags(text), method="explicit")

    best_bank: str | None = None
    best_score = 0
    for bank, keywords in DEFAULT_BANK_RULES.items():
        if bank not in allow:
            continue
        score = _hits(text, keywords)
        if score > best_score:
            best_score = score
            best_bank = bank

    if best_bank is None or best_score < ambiguity_threshold:
        raise AmbiguousRouteError()

    return Route(bank=best_bank, tags=derive_tags(text), method="auto")
