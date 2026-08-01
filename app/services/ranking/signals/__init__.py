"""
The twelve built-in ranking signals. Each lives in its own module so adding
one more is a self-contained, one-file change - implement the class here,
then register it in ../registry.py's `_REGISTRY` (or call
`register_signal(...)` at runtime). Nothing else needs to change.
"""

from .brand_similarity import BrandSimilaritySignal
from .category_similarity import CategorySimilaritySignal
from .freshness_signal import FreshnessSignal
from .popularity_signal import PopularitySignal
from .price_similarity import PriceSimilaritySignal
from .rating_signal import RatingSignal
from .review_count_signal import ReviewCountSignal
from .review_quality_signal import ReviewQualitySignal
from .search_history_signal import SearchHistorySignal
from .text_relevance_signal import TextRelevanceSignal
from .user_preference_signal import UserPreferenceSignal
from .visual_similarity import VisualSimilaritySignal

__all__ = [
    "BrandSimilaritySignal",
    "CategorySimilaritySignal",
    "FreshnessSignal",
    "PopularitySignal",
    "PriceSimilaritySignal",
    "RatingSignal",
    "ReviewCountSignal",
    "ReviewQualitySignal",
    "SearchHistorySignal",
    "TextRelevanceSignal",
    "UserPreferenceSignal",
    "VisualSimilaritySignal",
]
