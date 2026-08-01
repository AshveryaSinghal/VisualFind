"""
Tests for Tier 6 - selection (app/services/price_extraction/selection.py).

Covers the preference order (SELLING_PRICE > UNKNOWN > LIST_PRICE) and the
lowest-price tie-break within a role, which is the part of the pipeline
most likely to silently regress if someone "simplifies" it later (e.g. by
naively taking candidates[0]).
"""

from app.services.price_extraction.types import NormalizedCandidate, PriceRole
from app.services.price_extraction.selection import select_best_candidate

def _c(value: float, role: PriceRole) -> NormalizedCandidate:
    return NormalizedCandidate(value=value, currency="INR", role=role)

class TestSelectBestCandidate:
    def test_empty_list_returns_none(self):
        assert select_best_candidate([]) is None

    def test_single_candidate_is_returned(self):
        candidate = _c(1299, PriceRole.SELLING_PRICE)
        assert select_best_candidate([candidate]) is candidate

    def test_prefers_selling_price_over_unknown(self):
        selling = _c(1299, PriceRole.SELLING_PRICE)
        unknown = _c(999, PriceRole.UNKNOWN)
        result = select_best_candidate([unknown, selling])
        assert result is selling

    def test_prefers_selling_price_over_list_price(self):
        selling = _c(1299, PriceRole.SELLING_PRICE)
        list_price = _c(1999, PriceRole.LIST_PRICE)
        result = select_best_candidate([list_price, selling])
        assert result is selling

    def test_prefers_unknown_over_list_price(self):

        unknown = _c(1299, PriceRole.UNKNOWN)
        list_price = _c(1999, PriceRole.LIST_PRICE)
        result = select_best_candidate([list_price, unknown])
        assert result is unknown

    def test_falls_back_to_list_price_when_nothing_else_survived(self):

        list_price = _c(1999, PriceRole.LIST_PRICE)
        result = select_best_candidate([list_price])
        assert result is list_price

    def test_tie_break_prefers_lowest_price_within_same_role(self):
        cheaper = _c(899, PriceRole.SELLING_PRICE)
        pricier = _c(1299, PriceRole.SELLING_PRICE)
        result = select_best_candidate([pricier, cheaper])
        assert result is cheaper

    def test_does_not_let_a_decoy_full_price_beat_a_real_discount(self):

        candidates = [
            _c(2499, PriceRole.SELLING_PRICE),
            _c(1799, PriceRole.SELLING_PRICE),
            _c(2499, PriceRole.SELLING_PRICE),
        ]
        result = select_best_candidate(candidates)
        assert result.value == 1799
