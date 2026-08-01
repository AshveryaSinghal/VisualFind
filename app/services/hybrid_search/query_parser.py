"""
Turns a raw, free-typed hybrid-search query - "under ₹5000", "white
version", "same but leather", "Black Nike running shoes under 5000" - into
a budget constraint (applied as a hard price filter downstream) plus two
cleaned text variants:

  * `search_text`  - close to the original wording (budget phrase
    stripped), for the text-only pipeline (text_search_service.py), which
    already knows how to talk to real shopping-search engines and
    shouldn't be handed extra stopword-stripping it never asked for.
  * `relevance_text` - stopwords further stripped, for
    RankingContext.query_text / TextRelevanceSignal's bag-of-words match
    against an already visually-similar candidate pool in the hybrid
    (image + text) path.

Deliberately rule-based, no LLM call: this has to run inline on every
hybrid search request, including when Gemini isn't configured at all (see
app/services/ai/gemini_service.GeminiNotConfiguredError elsewhere in the
app) - a budget/color/material parse can never depend on an external AI
call succeeding.
"""

import re
from dataclasses import dataclass

_BUDGET_PATTERN = re.compile(
    r"(?:under|below|less than|cheaper than|within|up ?to)\s*"
    r"(₹|rs\.?|inr|\$|usd)?\s*"
    r"([\d,]+(?:\.\d+)?)\s*(k\b)?",
    re.IGNORECASE,
)

_CURRENCY_TOKENS = {
    "₹": "INR",
    "rs": "INR",
    "rs.": "INR",
    "inr": "INR",
    "$": "USD",
    "usd": "USD",
}

# Words that carry no product meaning of their own ("same but leather" ->
# just "leather" matters for text-relevance matching) - trimmed only from
# `relevance_text`, never from `search_text`.
_STOPWORDS = {
    "same", "but", "version", "the", "a", "an", "of", "with", "in", "for",
    "please", "show", "me", "find", "get", "and", "or", "is", "it", "that",
    "this", "one",
}


@dataclass
class ParsedTextQuery:
    raw: str
    search_text: str
    relevance_text: str
    budget_max: float | None = None
    currency: str | None = None

    @property
    def has_terms(self) -> bool:
        """Whether there's any free text left to search/match on, beyond
        just a budget constraint."""
        return bool(self.search_text.strip())


def parse_hybrid_text(text: str | None) -> ParsedTextQuery:
    raw = (text or "").strip()
    if not raw:
        return ParsedTextQuery(raw="", search_text="", relevance_text="")

    budget_max: float | None = None
    currency: str | None = None
    search_text = raw

    match = _BUDGET_PATTERN.search(raw)
    if match:
        currency_token = (match.group(1) or "").strip().lower()
        currency = _CURRENCY_TOKENS.get(currency_token)
        amount_text = match.group(2).replace(",", "")
        try:
            amount = float(amount_text)
        except ValueError:
            amount = None
        if amount is not None:
            if match.group(3):  # a trailing "k" -> thousands
                amount *= 1000
            budget_max = amount
            search_text = (raw[: match.start()] + raw[match.end():]).strip()

    relevance_text = _strip_stopwords(search_text)
    return ParsedTextQuery(
        raw=raw,
        search_text=search_text,
        relevance_text=relevance_text,
        budget_max=budget_max,
        currency=currency,
    )


def _strip_stopwords(text: str) -> str:
    words = [w for w in text.split() if w.strip(",.").lower() not in _STOPWORDS]
    cleaned = " ".join(words).strip()
    # Never let stopword-stripping erase everything a non-empty input had -
    # fall back to the un-stripped text so a signal downstream still has
    # *something* to compare, even if every word happened to be a stopword.
    return cleaned or text.strip()
