"""
Tests for app/services/hybrid_search/query_parser.py - pure string
parsing, no DB/network involved.
"""

from app.services.hybrid_search.query_parser import parse_hybrid_text


def test_empty_query_parses_to_all_empty_fields():
    parsed = parse_hybrid_text(None)
    assert parsed.raw == ""
    assert parsed.search_text == ""
    assert parsed.relevance_text == ""
    assert parsed.budget_max is None
    assert parsed.has_terms is False

    assert parse_hybrid_text("   ").raw == ""


def test_plain_query_with_no_budget_passes_through_unchanged():
    parsed = parse_hybrid_text("Black Nike running shoes")
    assert parsed.search_text == "Black Nike running shoes"
    assert parsed.relevance_text == "Black Nike running shoes"
    assert parsed.budget_max is None
    assert parsed.has_terms is True


def test_budget_only_query_extracts_amount_and_leaves_no_free_text():
    parsed = parse_hybrid_text("under ₹5000")
    assert parsed.budget_max == 5000.0
    assert parsed.currency == "INR"
    assert parsed.search_text == ""
    assert parsed.relevance_text == ""
    assert parsed.has_terms is False


def test_budget_is_stripped_out_of_a_mixed_query():
    parsed = parse_hybrid_text("Black Nike running shoes under 5000")
    assert parsed.budget_max == 5000.0
    assert parsed.search_text == "Black Nike running shoes"
    assert parsed.relevance_text == "Black Nike running shoes"


def test_k_suffix_is_treated_as_thousands():
    parsed = parse_hybrid_text("under 3k")
    assert parsed.budget_max == 3000.0


def test_dollar_and_below_phrasing_are_also_recognized():
    parsed = parse_hybrid_text("below $50")
    assert parsed.budget_max == 50.0
    assert parsed.currency == "USD"


def test_white_version_strips_the_filler_word_version_for_relevance():
    parsed = parse_hybrid_text("white version")
    assert parsed.search_text == "white version"  # kept intact for text-only pipelines
    assert parsed.relevance_text == "white"  # stopword-stripped for TextRelevanceSignal


def test_same_but_leather_strips_filler_words_down_to_the_real_attribute():
    parsed = parse_hybrid_text("same but leather")
    assert parsed.search_text == "same but leather"
    assert parsed.relevance_text == "leather"


def test_stopword_stripping_never_returns_an_empty_string_for_nonempty_input():
    parsed = parse_hybrid_text("same but")
    assert parsed.relevance_text == "same but"  # would've been empty otherwise; falls back to original


def test_comma_separated_amount_is_parsed_correctly():
    parsed = parse_hybrid_text("under Rs. 3,499")
    assert parsed.budget_max == 3499.0
    assert parsed.currency == "INR"
