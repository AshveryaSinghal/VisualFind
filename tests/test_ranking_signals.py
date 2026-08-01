"""
Unit tests for each of the twelve built-in ranking signals
(app/services/ranking/signals/). Each signal is exercised directly against
a hand-built RankingContext - no database, no engine, no product_index
involved - matching the "signals stay pure and testable" design goal.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.ranking.signals.brand_similarity import BrandSimilaritySignal
from app.services.ranking.signals.category_similarity import CategorySimilaritySignal
from app.services.ranking.signals.freshness_signal import FreshnessSignal
from app.services.ranking.signals.popularity_signal import PopularitySignal
from app.services.ranking.signals.price_similarity import PriceSimilaritySignal
from app.services.ranking.signals.rating_signal import RatingSignal
from app.services.ranking.signals.review_count_signal import ReviewCountSignal
from app.services.ranking.signals.review_quality_signal import ReviewQualitySignal
from app.services.ranking.signals.search_history_signal import SearchHistorySignal
from app.services.ranking.signals.text_relevance_signal import TextRelevanceSignal
from app.services.ranking.signals.user_preference_signal import UserPreferenceSignal
from app.services.ranking.signals.visual_similarity import VisualSimilaritySignal
from app.services.ranking.types import RankingContext, SearchHistorySnapshot, UserPreferenceSnapshot


def _candidate(**overrides):
    base = dict(
        title="Product",
        brand=None,
        category=None,
        price=None,
        rating=None,
        review_count=None,
        source=None,
        times_seen=None,
        created_at=None,
        updated_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- visual similarity ---

def test_visual_similarity_passes_through_precomputed_value():
    ctx = RankingContext(candidate=_candidate(), visual_similarity=0.87)
    outcome = VisualSimilaritySignal().score(ctx)
    assert outcome.value == 0.87


def test_visual_similarity_clamps_out_of_range_values():
    ctx = RankingContext(candidate=_candidate(), visual_similarity=1.5)
    assert VisualSimilaritySignal().score(ctx).value == 1.0


def test_visual_similarity_is_none_when_not_provided():
    ctx = RankingContext(candidate=_candidate())
    assert VisualSimilaritySignal().score(ctx).value is None


# --- brand similarity ---

def test_brand_similarity_exact_match_scores_one():
    ctx = RankingContext(candidate=_candidate(brand="Sony"), query_brand="sony")
    assert BrandSimilaritySignal().score(ctx).value == 1.0


def test_brand_similarity_substring_match_scores_partial():
    ctx = RankingContext(candidate=_candidate(brand="Sony Corp"), query_brand="Sony")
    assert BrandSimilaritySignal().score(ctx).value == 0.5


def test_brand_similarity_different_brands_scores_zero():
    ctx = RankingContext(candidate=_candidate(brand="Bose"), query_brand="Sony")
    assert BrandSimilaritySignal().score(ctx).value == 0.0


def test_brand_similarity_is_none_when_either_side_missing():
    assert BrandSimilaritySignal().score(RankingContext(candidate=_candidate(brand=None), query_brand="Sony")).value is None
    assert BrandSimilaritySignal().score(RankingContext(candidate=_candidate(brand="Sony"), query_brand=None)).value is None


# --- category similarity ---

def test_category_similarity_match_and_mismatch():
    match_ctx = RankingContext(candidate=_candidate(category="electronics"), query_category="electronics")
    mismatch_ctx = RankingContext(candidate=_candidate(category="footwear"), query_category="electronics")
    assert CategorySimilaritySignal().score(match_ctx).value == 1.0
    assert CategorySimilaritySignal().score(mismatch_ctx).value == 0.0


def test_category_similarity_is_none_when_either_side_missing():
    ctx = RankingContext(candidate=_candidate(category=None), query_category="electronics")
    assert CategorySimilaritySignal().score(ctx).value is None


# --- price similarity ---

def test_price_similarity_scores_close_prices_highly():
    ctx = RankingContext(candidate=_candidate(price=1000.0), query_price=1000.0)
    assert PriceSimilaritySignal().score(ctx).value == 1.0


def test_price_similarity_decays_with_relative_distance():
    close_ctx = RankingContext(candidate=_candidate(price=1050.0), query_price=1000.0)
    far_ctx = RankingContext(candidate=_candidate(price=5000.0), query_price=1000.0)
    close_score = PriceSimilaritySignal().score(close_ctx).value
    far_score = PriceSimilaritySignal().score(far_ctx).value
    assert close_score > far_score
    assert 0.0 <= far_score < close_score <= 1.0


def test_price_similarity_falls_back_to_budget_midpoint_when_no_query_price():
    ctx = RankingContext(
        candidate=_candidate(price=500.0),
        query_price=None,
        user_preferences=UserPreferenceSnapshot(budget_min=400.0, budget_max=600.0),
    )
    assert PriceSimilaritySignal().score(ctx).value == 1.0


def test_price_similarity_is_none_without_any_reference():
    ctx = RankingContext(candidate=_candidate(price=500.0))
    assert PriceSimilaritySignal().score(ctx).value is None


def test_price_similarity_is_none_without_candidate_price():
    ctx = RankingContext(candidate=_candidate(price=None), query_price=100.0)
    assert PriceSimilaritySignal().score(ctx).value is None


# --- rating ---

def test_rating_normalizes_to_zero_one_scale():
    ctx = RankingContext(candidate=_candidate(rating=4.5))
    assert RatingSignal().score(ctx).value == 0.9


def test_rating_is_none_when_missing():
    ctx = RankingContext(candidate=_candidate(rating=None))
    assert RatingSignal().score(ctx).value is None


# --- review count ---

def test_review_count_scores_the_pool_maximum_at_one():
    ctx = RankingContext(candidate=_candidate(review_count=500), reference_max_review_count=500)
    assert ReviewCountSignal().score(ctx).value == 1.0


def test_review_count_gives_lower_counts_a_lower_but_nonzero_score():
    ctx = RankingContext(candidate=_candidate(review_count=10), reference_max_review_count=1000)
    value = ReviewCountSignal().score(ctx).value
    assert 0.0 < value < 1.0


def test_review_count_is_none_when_missing():
    ctx = RankingContext(candidate=_candidate(review_count=None))
    assert ReviewCountSignal().score(ctx).value is None


# --- review quality ---

def test_review_quality_high_rating_with_many_reviews_scores_near_the_raw_rating():
    ctx = RankingContext(candidate=_candidate(rating=4.8, review_count=2000))
    value = ReviewQualitySignal().score(ctx).value
    assert 0.9 <= value <= 0.96  # pulled only slightly below the raw 0.96 by the confidence discount


def test_review_quality_discounts_a_high_rating_backed_by_few_reviews():
    few_reviews_ctx = RankingContext(candidate=_candidate(rating=5.0, review_count=2))
    many_reviews_ctx = RankingContext(candidate=_candidate(rating=5.0, review_count=2000))
    few_value = ReviewQualitySignal().score(few_reviews_ctx).value
    many_value = ReviewQualitySignal().score(many_reviews_ctx).value
    assert few_value < many_value  # same raw rating, but far less confidence with only 2 reviews
    assert few_value < 0.7


def test_review_quality_differs_from_plain_rating_and_review_count():
    # A 5.0 rating from a single review shouldn't score the same as RatingSignal's
    # raw normalization (1.0) - review_quality must discount for low confidence.
    ctx = RankingContext(candidate=_candidate(rating=5.0, review_count=1))
    rating_value = RatingSignal().score(ctx).value
    quality_value = ReviewQualitySignal().score(ctx).value
    assert rating_value == 1.0
    assert quality_value < rating_value


def test_review_quality_is_none_when_rating_or_count_missing():
    assert ReviewQualitySignal().score(RankingContext(candidate=_candidate(rating=None, review_count=50))).value is None
    assert ReviewQualitySignal().score(RankingContext(candidate=_candidate(rating=4.0, review_count=None))).value is None
    assert ReviewQualitySignal().score(RankingContext(candidate=_candidate(rating=4.0, review_count=0))).value is None


# --- user preference ---

def test_user_preference_full_match_scores_one():
    prefs = UserPreferenceSnapshot(
        favorite_categories=["electronics"],
        preferred_platforms=["Amazon"],
        budget_min=100.0,
        budget_max=2000.0,
    )
    candidate = _candidate(category="electronics", source="Amazon", price=1000.0)
    ctx = RankingContext(candidate=candidate, user_preferences=prefs)
    assert UserPreferenceSignal().score(ctx).value == 1.0


def test_user_preference_partial_match_scores_a_fraction():
    prefs = UserPreferenceSnapshot(favorite_categories=["electronics"], preferred_platforms=["Flipkart"])
    candidate = _candidate(category="electronics", source="Amazon")
    ctx = RankingContext(candidate=candidate, user_preferences=prefs)
    assert UserPreferenceSignal().score(ctx).value == 0.5


def test_user_preference_is_none_without_saved_preferences():
    ctx = RankingContext(candidate=_candidate(), user_preferences=None)
    assert UserPreferenceSignal().score(ctx).value is None


def test_user_preference_is_none_when_no_dimensions_are_configured():
    ctx = RankingContext(candidate=_candidate(), user_preferences=UserPreferenceSnapshot())
    assert UserPreferenceSignal().score(ctx).value is None


# --- search history ---

def test_search_history_rewards_frequently_searched_brand():
    history = SearchHistorySnapshot(brand_counts={"sony": 5, "bose": 5})
    ctx = RankingContext(candidate=_candidate(brand="Sony"), search_history=history)
    assert SearchHistorySignal().score(ctx).value == 1.0  # 50% share saturates above the 1/3 threshold


def test_search_history_scores_zero_for_unrelated_brand():
    history = SearchHistorySnapshot(brand_counts={"sony": 5})
    ctx = RankingContext(candidate=_candidate(brand="Nike"), search_history=history)
    assert SearchHistorySignal().score(ctx).value == 0.0


def test_search_history_is_none_without_any_history():
    ctx = RankingContext(candidate=_candidate(brand="Sony"), search_history=None)
    assert SearchHistorySignal().score(ctx).value is None


# --- popularity ---

def test_popularity_scores_the_pool_maximum_at_one():
    ctx = RankingContext(candidate=_candidate(times_seen=20), reference_max_times_seen=20)
    assert PopularitySignal().score(ctx).value == 1.0


def test_popularity_is_none_when_never_seen():
    ctx = RankingContext(candidate=_candidate(times_seen=None))
    assert PopularitySignal().score(ctx).value is None


# --- freshness ---

def test_freshness_scores_just_updated_item_near_one():
    now = datetime.now(timezone.utc)
    ctx = RankingContext(candidate=_candidate(updated_at=now), reference_now=now)
    assert FreshnessSignal().score(ctx).value == 1.0


def test_freshness_decays_for_older_items():
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=30)  # exactly one half-life
    ctx = RankingContext(candidate=_candidate(updated_at=old), reference_now=now)
    assert abs(FreshnessSignal().score(ctx).value - 0.5) < 1e-6


def test_freshness_falls_back_to_created_at_when_never_updated():
    now = datetime.now(timezone.utc)
    ctx = RankingContext(
        candidate=_candidate(updated_at=None, created_at=now), reference_now=now
    )
    assert FreshnessSignal().score(ctx).value == 1.0


def test_freshness_is_none_without_any_timestamp():
    ctx = RankingContext(candidate=_candidate(updated_at=None, created_at=None))
    assert FreshnessSignal().score(ctx).value is None


# --- text relevance ---

def test_text_relevance_is_none_without_a_query():
    ctx = RankingContext(candidate=_candidate(title="Sony WH-1000XM5 Headphones"))
    assert TextRelevanceSignal().score(ctx).value is None


def test_text_relevance_scores_full_overlap_at_one():
    ctx = RankingContext(candidate=_candidate(title="White Nike Running Shoes"), query_text="white")
    assert TextRelevanceSignal().score(ctx).value == 1.0


def test_text_relevance_scores_partial_overlap_as_a_fraction():
    ctx = RankingContext(candidate=_candidate(title="White Nike Running Shoes"), query_text="white leather")
    assert TextRelevanceSignal().score(ctx).value == 0.5  # only "white" overlaps of the two query terms


def test_text_relevance_matches_leather_variant_over_non_matching_candidate():
    leather_ctx = RankingContext(candidate=_candidate(title="Nike Leather Sneakers"), query_text="leather")
    other_ctx = RankingContext(candidate=_candidate(title="Nike Mesh Sneakers"), query_text="leather")
    assert TextRelevanceSignal().score(leather_ctx).value > TextRelevanceSignal().score(other_ctx).value


def test_text_relevance_also_matches_brand_and_category_fields():
    ctx = RankingContext(candidate=_candidate(title="Running Shoes", brand="Nike"), query_text="nike")
    assert TextRelevanceSignal().score(ctx).value == 1.0


def test_text_relevance_is_zero_when_candidate_has_no_text_fields():
    ctx = RankingContext(candidate=_candidate(title=None, brand=None, category=None), query_text="leather")
    assert TextRelevanceSignal().score(ctx).value == 0.0
