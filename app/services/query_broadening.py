"""
Fallback query broadening for the AI Shopping Assistant / smart search bar.

The exact-match search always runs first (see text_search_service.py). Only
if it returns zero trusted-platform matches do we try these, in order, and
stop at the first one that finds anything - so we go no broader than we have
to before showing "closest alternatives" instead of an exact match.
"""

import re

_FILLER_WORDS = {
    "best", "cheap", "cheapest", "affordable", "good", "top", "under",
    "below", "within", "budget", "for", "a", "an", "the", "with", "my",
    "buy", "online", "please", "need", "want", "looking",
}

_CURRENCY_OR_NUMBER = re.compile(r"^(rs\.?|inr|₹|\$|usd)?\d[\d,.]*$", re.IGNORECASE)

def _strip_price_and_filler(query: str) -> list[str]:
    tokens = query.split()
    kept = []
    for tok in tokens:
        bare = tok.strip(",.")
        if _CURRENCY_OR_NUMBER.match(bare):
            continue
        if bare.lower() in _FILLER_WORDS:
            continue
        kept.append(tok)
    return kept

def broaden_query(query: str) -> list[str]:
    """
    Returns an ordered list of progressively broader candidate queries to
    retry, most-specific first. Never includes the original query itself
    (the caller already tried that) and never returns an empty string.
    """
    query = query.strip()
    if not query:
        return []

    candidates: list[str] = []

    stripped_tokens = _strip_price_and_filler(query)
    stripped = " ".join(stripped_tokens).strip()
    if stripped and stripped.lower() != query.lower():
        candidates.append(stripped)

    base_tokens = stripped_tokens or query.split()
    for keep in range(min(len(base_tokens), 4) - 1, 0, -1):
        shortened = " ".join(base_tokens[:keep]).strip()
        if shortened and shortened.lower() not in {c.lower() for c in candidates} and shortened.lower() != query.lower():
            candidates.append(shortened)

    return candidates
