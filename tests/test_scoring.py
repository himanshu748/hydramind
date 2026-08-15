"""Tests for the transparent recall relevance scorer."""

from hydramind.tools import keyword_overlap_score


def test_keyword_overlap_is_transparent_and_bounded() -> None:
    assert keyword_overlap_score("HydraDB trust graph", "HydraDB graph memory") == 2 / 3
    assert keyword_overlap_score("unrelated tokens", "HydraDB graph memory") == 0.0
    assert keyword_overlap_score("", "anything") == 0.0
    content = "The production routing policy requires direct traffic."
    assert keyword_overlap_score("How should production route?", content) == 1.0
    assert keyword_overlap_score("Who owns the production routing policy?", content) == 0.75
