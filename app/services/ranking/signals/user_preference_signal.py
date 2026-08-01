"""
User preference fit signal: rewards candidates that line up with a user's
own saved preferences (see app/services/preferences_service.py) - favorite
category, preferred platform, and stated budget.

Each dimension the user has actually configured contributes one point of
an N-point scale, where N is however many of those three dimensions are
set; a dimension they've never touched is left out entirely rather than
counted against a candidate (a user with no favorite categories saved
shouldn't have every candidate penalized for "not matching a favorite
category" that doesn't exist).
"""

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome


class UserPreferenceSignal(RankingSignal):
    name = "user_preference"
    default_weight = 1.25

    def score(self, context: RankingContext) -> SignalOutcome:
        prefs = context.user_preferences
        if prefs is None:
            return SignalOutcome(None, "No saved preferences for this user.")

        dimensions = 0
        hits = 0
        matched: list[str] = []

        if prefs.favorite_categories:
            dimensions += 1
            candidate_category = getattr(context.candidate, "category", None)
            if candidate_category and candidate_category in prefs.favorite_categories:
                hits += 1
                matched.append("favorite category")

        if prefs.preferred_platforms:
            dimensions += 1
            candidate_platform = getattr(context.candidate, "source", None)
            if candidate_platform and candidate_platform in prefs.preferred_platforms:
                hits += 1
                matched.append("preferred platform")

        if prefs.budget_min is not None or prefs.budget_max is not None:
            dimensions += 1
            candidate_price = getattr(context.candidate, "price", None)
            if candidate_price is not None and self._within_budget(candidate_price, prefs):
                hits += 1
                matched.append("within budget")

        if dimensions == 0:
            return SignalOutcome(None, "No preference dimensions (category/platform/budget) are set.")

        value = hits / dimensions
        detail = ", ".join(matched) if matched else "no saved preferences"
        return SignalOutcome(value, f"Matches {hits}/{dimensions} saved preference(s): {detail}.")

    @staticmethod
    def _within_budget(price: float, prefs) -> bool:
        if prefs.budget_min is not None and price < prefs.budget_min:
            return False
        if prefs.budget_max is not None and price > prefs.budget_max:
            return False
        return True
