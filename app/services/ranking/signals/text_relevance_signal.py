"""
Text relevance signal: rewards candidates whose title/brand/category
overlaps with the free-text terms of a hybrid (image + text) or text-only
search - e.g. "white version", "same but leather", "Black Nike running
shoes". See app/services/hybrid_search/query_parser.py for how a raw typed
query becomes `RankingContext.query_text` - a budget phrase like "under
5000" is extracted separately there and applied as a hard price filter
upstream (see product_index_service.rank_matches), not scored here.

Deliberately simple bag-of-words overlap - no embeddings, no external NLP
call. This only needs to break ties within an already visually-similar
candidate pool (see product_index_service.rank_matches/rank_similar), not
act as a standalone text search engine - that job belongs to
text_search_service.py for a text-only query with no image at all.
"""

import re

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(_WORD_RE.findall(text.lower()))


class TextRelevanceSignal(RankingSignal):
    name = "text_relevance"
    # Weighted on par with visual similarity by default - in a hybrid
    # search the text half of the query (a color, a material, "under
    # 5000") is usually the whole reason the person typed anything at all,
    # not a minor tiebreaker.
    default_weight = 2.5

    def score(self, context: RankingContext) -> SignalOutcome:
        query_tokens = _tokenize(context.query_text)
        if not query_tokens:
            return SignalOutcome(None, "No text query terms to match against.")

        candidate = context.candidate
        haystack = " ".join(
            str(part)
            for part in (
                getattr(candidate, "title", None),
                getattr(candidate, "brand", None),
                getattr(candidate, "category", None),
            )
            if part
        )
        candidate_tokens = _tokenize(haystack)
        if not candidate_tokens:
            return SignalOutcome(0.0, "This candidate has no text fields to match against.")

        overlap = query_tokens & candidate_tokens
        if not overlap:
            return SignalOutcome(0.0, f"No overlap with query term(s): {', '.join(sorted(query_tokens))}.")

        value = len(overlap) / len(query_tokens)
        return SignalOutcome(value, f"Matches query term(s): {', '.join(sorted(overlap))}.")
