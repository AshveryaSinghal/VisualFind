"""
Cleans up the `structured_query` dict Gemini produced in intent_parser.py
into (a) the exact text string to hand to the real product-search pipeline,
and (b) a small human-readable summary for the recommendation prompt / UI.

This is intentionally dumb and defensive: Gemini's structured output is
already schema-constrained, but this module is the last line of defense
against blank/garbage values before they reach the search pipeline.
"""

from dataclasses import dataclass

@dataclass
class ExtractedPreferences:
    category: str | None
    budget_max: float | None
    budget_currency: str
    brand: str | None
    preferences: list[str]
    search_text: str

    def as_requirements_summary(self) -> str:
        """Short human-readable line describing what the user asked for -
        fed to the recommendation engine so it can explain *why* a product
        matches, without re-deriving it from the raw search string."""
        parts = []
        if self.category:
            parts.append(f"Category: {self.category}")
        if self.budget_max:
            parts.append(f"Budget: {self.budget_currency} {self.budget_max:g} max")
        if self.brand:
            parts.append(f"Preferred brand: {self.brand}")
        if self.preferences:
            parts.append("Preferences: " + ", ".join(self.preferences))
        return "; ".join(parts) if parts else self.search_text

def extract(structured_query: dict) -> ExtractedPreferences:
    category = _clean_str(structured_query.get("category"))
    brand = _clean_str(structured_query.get("brand"))
    budget_currency = _clean_str(structured_query.get("budget_currency")) or "INR"

    budget_max = structured_query.get("budget_max")
    try:
        budget_max = float(budget_max) if budget_max not in (None, "") else None
    except (TypeError, ValueError):
        budget_max = None

    raw_preferences = structured_query.get("preferences") or []
    preferences = [p.strip() for p in raw_preferences if isinstance(p, str) and p.strip()]

    search_text = _clean_str(structured_query.get("search_text"))
    if not search_text:

        fallback_bits = [category] + preferences
        if budget_max:
            fallback_bits.append(f"under {budget_currency} {budget_max:g}")
        search_text = " ".join(b for b in fallback_bits if b).strip()

    return ExtractedPreferences(
        category=category,
        budget_max=budget_max,
        budget_currency=budget_currency,
        brand=brand,
        preferences=preferences,
        search_text=search_text,
    )

def _clean_str(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
