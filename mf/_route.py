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
import re
import unicodedata
from typing import Iterable

# Banks that exist on the instance and are approved by the taxonomy. Verified
# against GET /v1/default/banks (2026-08-30). The facade never creates a bank,
# so this is the hard boundary for explicit targets.
BANK_ALLOWLIST: tuple[str, ...] = (
    "global-user",
    "infra",
    "projects",
    "business",
    "work",
    "medical",
    "product-rigplane",
)

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
        "memory bank", "mental model", "auto-retain", "bank inventory",
        "unifi", "udm", "home assistant", "hass", "ollama", "ha proxy",
    ],
    "business": [
        "business strategy", "positioning", "pricing", "customer", "partner",
        "go-to-market", "business plan",
    ],
    "work": [
        "serverstack", "employer", "colleague", "work project", "professional work",
    ],
    "medical": [
        "medical", "diagnosis", "diagnoses", "clinic", "clinics",
        "doctor", "doctors", "prescription", "prescriptions",
        "personal health", "health record", "health records",
        "medication", "medications", "lab result", "lab results", "lab work",
        "blood test", "blood tests",
    ],
    "product-rigplane": ["rigplane"],
}

# Tag prefixes we may emit deterministically. Values are derived from keywords.
TAG_KEYWORDS: dict[str, list[str]] = {
    "domain:memory": ["hindsight", "common-memory", "memory", "recall", "retain"],
    "domain:infra": ["infra", "infrastructure", "ansible", "deploy", "semaphore", "nginx", "haproxy", "unifi", "home assistant", "hass"],
    "project:common-memory": ["common-memory", "hindsight", "memory"],
    "service:ai-gateway": ["litellm", "gateway", "mcp", "ai-gateway"],
}

DEFAULT_AMBIGUITY_THRESHOLD = 1  # at least one keyword hit required to route

# Safety-first detector independent of ordinary bank scoring. Compact matching
# tolerates pluralization, inserted separators, and common Cyrillic homoglyphs
# from browser/PDF text while avoiding a bare operational "health check".
_MEDICAL_CONFUSABLES = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
        "у": "y", "х": "x", "і": "i", "ј": "j", "к": "k",
        "м": "m", "т": "t", "в": "b", "н": "h",
    }
)
_MEDICAL_COMPACT_STEMS = (
    "medical", "healthcare", "healthinsurance",
    "diagnosis", "diagnoses", "diagnosed",
    "clinic", "doctor", "prescription", "medication", "patient", "hospital",
    "therapy", "bloodtest", "labresult", "labwork",
)
_MEDICAL_HEALTH_PHRASES = (
    "my health", "personal health", "mental health", "family health",
    "health condition", "health record", "health concern", "health issue",
    "health tracking",
)


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


def _normalize_route_text(value: str) -> str:
    """Normalize invisible formatting and separator variants for routing."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    # Remove zero-width/format controls inside words (including soft hyphen) so
    # copied browser text cannot hide a sensitive keyword from the classifier.
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Cf")
    # Treat underscores, all Unicode dash punctuation, MINUS SIGN, and HYPHEN
    # BULLET as equivalent separators, then collapse all whitespace variants.
    normalized = "".join(
        " " if ch == "_" or unicodedata.category(ch) == "Pd" or ch in {"\u2212", "\u2043"} else ch
        for ch in normalized
    )
    return " ".join(normalized.split())


def _has_sensitive_medical_signal(normalized_text: str) -> bool:
    deconfused = normalized_text.translate(_MEDICAL_CONFUSABLES)
    if any(phrase in deconfused for phrase in _MEDICAL_HEALTH_PHRASES):
        return True
    compact = re.sub(r"[^0-9a-z]", "", deconfused)
    return any(stem in compact for stem in _MEDICAL_COMPACT_STEMS)


def _contains_normalized_keyword(haystack: str, keyword: str) -> bool:
    needle = _normalize_route_text(keyword)
    if not needle:
        return False
    pattern = rf"(?<![0-9a-z]){re.escape(needle)}(?![0-9a-z])"
    return re.search(pattern, haystack) is not None


def _contains_keyword(text: str, keyword: str) -> bool:
    """Match a normalized keyword as an ASCII-token-bounded phrase."""
    return _contains_normalized_keyword(_normalize_route_text(text), keyword)


def _hits_normalized(haystack: str, keywords: Iterable[str]) -> int:
    return sum(1 for kw in keywords if _contains_normalized_keyword(haystack, kw))


def _hits(text: str, keywords: Iterable[str]) -> int:
    return _hits_normalized(_normalize_route_text(text), keywords)


def derive_tags(text: str) -> list[str]:
    """Deterministically derive tags from keyword presence (dedup, ordered)."""
    haystack = _normalize_route_text(text)
    tags: list[str] = []
    for tag, keywords in TAG_KEYWORDS.items():
        if _hits_normalized(haystack, keywords):
            tags.append(tag)
    return tags


def route(
    text: str,
    bank_allowlist: Iterable[str] = BANK_ALLOWLIST,
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

    normalized_text = _normalize_route_text(text)
    # Fail closed toward the sensitive boundary: explicit medical evidence must
    # never be outscored by incidental operational words such as docker/vault.
    sensitive_medical = _has_sensitive_medical_signal(normalized_text) or (
        _hits_normalized(normalized_text, DEFAULT_BANK_RULES["medical"]) > 0
    )
    if sensitive_medical:
        if "medical" not in allow:
            raise AmbiguousRouteError(
                "Sensitive medical content detected but the medical bank is outside the allowed target scope"
            )
        return Route(
            bank="medical", tags=["sensitivity:restricted"], method="auto"
        )

    best_bank: str | None = None
    best_score = 0
    for bank, keywords in DEFAULT_BANK_RULES.items():
        if bank not in allow or bank == "medical":
            continue
        score = _hits_normalized(normalized_text, keywords)
        if score > best_score:
            best_score = score
            best_bank = bank
        elif score == best_score and score > 0 and best_bank == "global-user":
            # Prefer a specific domain over personal memory on an equal score.
            best_bank = bank

    if best_bank is None or best_score < ambiguity_threshold:
        raise AmbiguousRouteError()

    return Route(bank=best_bank, tags=derive_tags(text), method="auto")
