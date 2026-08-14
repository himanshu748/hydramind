"""Unit tests for the intentionally small conflict heuristic."""

from __future__ import annotations

import pytest

from hydramind.conflict import detect_conflict_reason


@pytest.mark.parametrize(
    ("new_content", "old_content", "expected_words"),
    [
        ("Never cache credentials.", "Always cache credentials.", "always"),
        ("The API must not retry.", "The API must retry.", "must not"),
        ("Use indirect routing.", "Use direct routing.", "indirect"),
        ("The feature is disabled.", "The feature is enabled.", "disabled"),
        ("Uploads are forbidden.", "Uploads are required.", "forbidden"),
        ("The flag is not active.", "The flag is active.", "negates"),
    ],
)
def test_detects_opposite_polarity(
    new_content: str,
    old_content: str,
    expected_words: str,
) -> None:
    reason = detect_conflict_reason(new_content, old_content)
    assert reason is not None
    assert expected_words in reason.casefold()


def test_does_not_flag_unrelated_same_polarity_statements() -> None:
    assert (
        detect_conflict_reason(
            "The service should emit structured logs.",
            "The service should expose health metrics.",
        )
        is None
    )


def test_does_not_flag_opposite_modals_about_different_claims() -> None:
    assert (
        detect_conflict_reason(
            "The service should not log secrets.",
            "The service should cache responses.",
        )
        is None
    )


def test_polarity_detection_is_symmetric() -> None:
    left = "The SDK cannot use indirect routing."
    right = "The SDK can use indirect routing."
    assert detect_conflict_reason(left, right) is not None
    assert detect_conflict_reason(right, left) is not None
