"""
Tests for Tier 5 - validation (app/services/price_extraction/validation.py).

This is the layer that decides whether a numeric value that parsed fine is
actually a plausible selling price, or a shipping fee / EMI figure /
discount percentage / coupon amount / obvious sentinel value masquerading
as one. It's pure and I/O-free, so every case here is a plain input/output
check -- no mocking needed.
"""

import math

from app.services.price_extraction.types import NormalizedCandidate, PriceRole
from app.services.price_extraction.validation import (
    filter_valid_candidates,
    infer_role_from_text,
    is_plausible_amount,
    is_valid_selling_price_candidate,
)

def _candidate(value: float, role: PriceRole = PriceRole.UNKNOWN) -> NormalizedCandidate:
    return NormalizedCandidate(value=value, currency="INR", role=role)

class TestIsPlausibleAmount:
    def test_rejects_zero_and_one(self):

        assert is_plausible_amount(0) is False
        assert is_plausible_amount(1) is False

    def test_rejects_negative(self):
        assert is_plausible_amount(-499) is False

    def test_rejects_nan(self):
        assert is_plausible_amount(math.nan) is False

    def test_rejects_none(self):
        assert is_plausible_amount(None) is False

    def test_rejects_absurd_sentinel_ceiling(self):
        assert is_plausible_amount(999_999_999) is False

    def test_rejects_below_minimum_plausible_floor(self):

        assert is_plausible_amount(1.5) is False

    def test_accepts_cheap_but_real_accessory_price(self):

        assert is_plausible_amount(2) is True
        assert is_plausible_amount(49) is True

    def test_accepts_typical_product_price(self):
        assert is_plausible_amount(1299.0) is True

class TestInferRoleFromText:
    def test_detects_shipping(self):
        assert infer_role_from_text("Delivery Fee", None) == PriceRole.SHIPPING

    def test_detects_emi(self):
        assert infer_role_from_text(None, "starting at ₹499/mo EMI") == PriceRole.EMI_INSTALLMENT

    def test_detects_discount_percent_via_keyword(self):
        assert infer_role_from_text("You Save", None) == PriceRole.DISCOUNT_PERCENT

    def test_detects_discount_percent_via_regex_fallback(self):

        assert infer_role_from_text(None, "flat 30% off today") == PriceRole.DISCOUNT_PERCENT

    def test_detects_coupon(self):
        assert infer_role_from_text("Promo Code", None) == PriceRole.COUPON

    def test_detects_list_price_mrp(self):
        assert infer_role_from_text("MRP", None) == PriceRole.LIST_PRICE

    def test_falls_back_to_unknown_for_plain_price_label(self):
        assert infer_role_from_text("Price", "₹1,299") == PriceRole.UNKNOWN

    def test_falls_back_to_unknown_for_empty_text(self):
        assert infer_role_from_text(None, None) == PriceRole.UNKNOWN

class TestIsValidSellingPriceCandidate:
    def test_rejects_implausible_amount_regardless_of_role(self):
        assert is_valid_selling_price_candidate(_candidate(0, PriceRole.UNKNOWN)) is False

    def test_rejects_shipping_role_even_if_numerically_plausible(self):
        assert is_valid_selling_price_candidate(_candidate(99, PriceRole.SHIPPING)) is False

    def test_rejects_emi_role(self):
        assert is_valid_selling_price_candidate(_candidate(499, PriceRole.EMI_INSTALLMENT)) is False

    def test_rejects_discount_percent_role(self):
        assert is_valid_selling_price_candidate(_candidate(30, PriceRole.DISCOUNT_PERCENT)) is False

    def test_rejects_coupon_role(self):
        assert is_valid_selling_price_candidate(_candidate(100, PriceRole.COUPON)) is False

    def test_accepts_selling_price_role(self):
        assert is_valid_selling_price_candidate(_candidate(1299, PriceRole.SELLING_PRICE)) is True

    def test_accepts_list_price_role_numerically_plausible(self):

        assert is_valid_selling_price_candidate(_candidate(1999, PriceRole.LIST_PRICE)) is True

    def test_accepts_unknown_role_numerically_plausible(self):
        assert is_valid_selling_price_candidate(_candidate(799, PriceRole.UNKNOWN)) is True

class TestFilterValidCandidates:
    def test_keeps_only_valid_candidates(self):
        candidates = [
            _candidate(1299, PriceRole.SELLING_PRICE),
            _candidate(99, PriceRole.SHIPPING),
            _candidate(0, PriceRole.UNKNOWN),
            _candidate(1999, PriceRole.LIST_PRICE),
        ]
        result = filter_valid_candidates(candidates)
        assert [c.value for c in result] == [1299, 1999]

    def test_empty_input_returns_empty_list(self):
        assert filter_valid_candidates([]) == []

    def test_all_invalid_returns_empty_list(self):
        candidates = [_candidate(0), _candidate(-5), _candidate(99, PriceRole.SHIPPING)]
        assert filter_valid_candidates(candidates) == []
