"""Readable, replaceable conflict detection heuristics for memory statements."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PolarityPair:
    """Two phrases that plausibly express opposite claims about one entity."""

    positive_label: str
    negative_label: str
    positive_pattern: re.Pattern[str]
    negative_pattern: re.Pattern[str]


def _pattern(expression: str) -> re.Pattern[str]:
    return re.compile(expression, re.IGNORECASE)


POLARITY_PAIRS: tuple[PolarityPair, ...] = (
    PolarityPair("always", "never", _pattern(r"\balways\b"), _pattern(r"\bnever\b")),
    PolarityPair(
        "must",
        "must not",
        _pattern(r"\bmust\b(?!\s+not\b)"),
        _pattern(r"\bmust\s+not\b|\bmustn't\b"),
    ),
    PolarityPair(
        "should",
        "should not",
        _pattern(r"\bshould\b(?!\s+not\b)"),
        _pattern(r"\bshould\s+not\b|\bshouldn't\b"),
    ),
    PolarityPair(
        "can",
        "cannot",
        _pattern(r"\bcan\b(?!\s+not\b)"),
        _pattern(r"\bcannot\b|\bcan\s+not\b|\bcan't\b"),
    ),
    PolarityPair(
        "direct",
        "indirect",
        _pattern(r"\bdirect\b"),
        _pattern(r"\bindirect\b"),
    ),
    PolarityPair(
        "enabled",
        "disabled",
        _pattern(r"\benabled?\b"),
        _pattern(r"\bdisabled?\b"),
    ),
    PolarityPair(
        "required",
        "forbidden",
        _pattern(r"\brequired?\b"),
        _pattern(r"\bforbidden\b|\bprohibited\b"),
    ),
    PolarityPair(
        "allow",
        "deny",
        _pattern(r"\ballow(?:s|ed|ing)?\b"),
        _pattern(r"\bdeny|denies|denied|denying|disallow(?:s|ed|ing)?\b"),
    ),
    PolarityPair("true", "false", _pattern(r"\btrue\b"), _pattern(r"\bfalse\b")),
    PolarityPair(
        "present",
        "absent",
        _pattern(r"\bpresent\b"),
        _pattern(r"\babsent\b|\bmissing\b"),
    ),
    PolarityPair(
        "use",
        "avoid",
        _pattern(r"\buse(?:s|d|ing)?\b"),
        _pattern(r"\bavoid(?:s|ed|ing)?\b"),
    ),
)

_NEGATED_TERM = re.compile(r"\b(?:not|isn't|aren't|doesn't|don't)\s+([a-z][a-z0-9_-]+)\b")
_GENERIC_NEGATION_EXCLUSIONS = {"also", "just", "necessarily", "only"}
_WORD = re.compile(r"[a-z0-9_-]+")
_POLARITY_WORDS = {
    "always",
    "never",
    "must",
    "not",
    "should",
    "can",
    "cannot",
    "direct",
    "indirect",
    "enabled",
    "enable",
    "disabled",
    "disable",
    "required",
    "require",
    "forbidden",
    "allow",
    "deny",
    "true",
    "false",
    "present",
    "absent",
    "missing",
    "use",
    "avoid",
}
_CLAIM_STOPWORDS = {
    "a",
    "an",
    "and",
    "api",
    "app",
    "application",
    "are",
    "agent",
    "be",
    "is",
    "it",
    "of",
    "sdk",
    "service",
    "system",
    "the",
    "to",
}


def detect_conflict_reason(new_content: str, existing_content: str) -> str | None:
    """Return a plain-language reason when two same-entity claims look opposed."""

    new_text = _normalize(new_content)
    existing_text = _normalize(existing_content)

    for pair in POLARITY_PAIRS:
        new_positive = pair.positive_pattern.search(new_text) is not None
        new_negative = pair.negative_pattern.search(new_text) is not None
        old_positive = pair.positive_pattern.search(existing_text) is not None
        old_negative = pair.negative_pattern.search(existing_text) is not None
        opposite = (new_positive and old_negative) or (new_negative and old_positive)
        if opposite and _shares_claim_terms(new_text, existing_text):
            return (
                "Opposite polarity for the same entity: "
                f"'{pair.positive_label}' versus '{pair.negative_label}'."
            )

    generic_reason = _generic_negation_reason(new_text, existing_text)
    if generic_reason is not None:
        return generic_reason
    return None


def _shares_claim_terms(left: str, right: str) -> bool:
    """Require polarity opposites to describe at least one shared proposition term."""

    ignored = _POLARITY_WORDS | _CLAIM_STOPWORDS
    left_terms = {term for term in _WORD.findall(left) if term not in ignored}
    right_terms = {term for term in _WORD.findall(right) if term not in ignored}
    return bool(left_terms & right_terms)


def _generic_negation_reason(left: str, right: str) -> str | None:
    for negated_text, affirmative_text in ((left, right), (right, left)):
        for term in _NEGATED_TERM.findall(negated_text):
            if term in _GENERIC_NEGATION_EXCLUSIONS:
                continue
            affirmative = re.search(rf"(?<!not\s)\b{re.escape(term)}\b", affirmative_text)
            if affirmative is not None and not re.search(
                rf"\bnot\s+{re.escape(term)}\b", affirmative_text
            ):
                return (
                    "Opposite polarity for the same entity: "
                    f"one statement negates '{term}' and the other affirms it."
                )
    return None


def _normalize(content: str) -> str:
    return " ".join(content.casefold().split())
