"""
Tier 4 - Normalization.

Converts every PriceCandidate (whatever shape/tier it came from - a SerpApi
JSON field, a JSON-LD "price" string, an OpenGraph meta tag, visible DOM
text) into a common numeric float plus an ISO-4217-ish currency code.

Number-parsing is delegated to price_utils.extract_numeric_price (the one
place that owns "how do we turn a messy price string into a float").
Currency resolution is delegated to CurrencyResolverService (the one place
that owns "how do we turn whatever currency signal we found into an ISO
code, and what do we do when we found none") - this module's job is
specifically routing each candidate's currency signal to the right tier of
that resolver based on where the candidate came from (its `label`).
"""

from app.services.currency_resolver import currency_resolver
from app.services.price_extraction.types import NormalizedCandidate, PriceCandidate
from app.services.price_utils import extract_numeric_price

_JSON_LD_LABEL_PREFIX = "json_ld."
_OPENGRAPH_LABEL_PREFIX = "opengraph."
_MICRODATA_LABEL_PREFIX = "microdata."
_META_LABEL_PREFIX = "meta."

def _currency_kwargs_for_label(label: str | None, raw_currency: str | None) -> dict:
    """Buckets a candidate's raw_currency into the right resolver tier."""
    label = label or ""
    if label.startswith(_JSON_LD_LABEL_PREFIX):
        return {"json_ld_currency": raw_currency}
    if label.startswith(_MICRODATA_LABEL_PREFIX) or label.startswith(_META_LABEL_PREFIX):
        return {"structured_metadata_currency": raw_currency}
    if label.startswith(_OPENGRAPH_LABEL_PREFIX):
        return {"opengraph_currency": raw_currency}
    return {"price_currency": raw_currency}

def normalize_candidate(
    candidate: PriceCandidate,
    reference_url: str | None = None,
    platform: str | None = None,
) -> NormalizedCandidate | None:
    """
    Returns a NormalizedCandidate, or None if the raw value couldn't be
    parsed into a number at all (e.g. empty string, "Contact for price").
    Never raises.
    """
    try:
        value = extract_numeric_price(candidate.raw_price)
    except Exception:
        value = None

    if value is None:
        return None

    currency = currency_resolver.resolve(
        **_currency_kwargs_for_label(candidate.label, candidate.raw_currency),
        price_text=str(candidate.raw_price),
        platform=platform,
        url=reference_url,
    )

    return NormalizedCandidate(
        value=value,
        currency=currency,
        role=candidate.role,
        label=candidate.label,
        context=candidate.context,
    )

def normalize_candidates(
    candidates: list[PriceCandidate],
    reference_url: str | None = None,
    platform: str | None = None,
) -> list[NormalizedCandidate]:
    normalized = []
    for candidate in candidates:
        result = normalize_candidate(candidate, reference_url, platform)
        if result is not None:
            normalized.append(result)
    return normalized
