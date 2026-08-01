"""
Shared text-cleaning helpers.

Product titles coming out of Google Lens are often raw scraped <title> tags
from the source retailer page, which routinely carry boilerplate the actual
product name doesn't have: a leading "Buy ", a leading "amazon.com : ", a
trailing "| Ajio.com", or - the one that actually broke shopping-query
matching in practice - a bare rating fragment glued onto the end followed by
an ellipsis, e.g. "...Tinted Lip Balm Moisturizes & Nourishes 4.5 ...".
That garbled tail becomes part of the text sent to Google Shopping and
measurably hurts match quality, so it's stripped before the text is used
for anything (search query *or* the "best guess" label shown to the user).
"""

import re

_LEADING_BUY_PATTERN = re.compile(r"^\s*buy\s+", re.IGNORECASE)
_LEADING_SITE_PREFIX_PATTERN = re.compile(r"^\s*[\w.-]+\.(com|in)\s*[:\-]\s*", re.IGNORECASE)

_ELLIPSIS_PATTERN = re.compile(r"\.{3}|…")
_TRAILING_SITE_SUFFIX_PATTERN = re.compile(r"\s*[|\-]\s*[\w.-]+\.(com|in)\s*$", re.IGNORECASE)

_TRAILING_RATING_PATTERN = re.compile(r"\s+[0-5]\.\d\s*$")

def clean_product_title(text: str | None) -> str | None:
    """Strips retailer-page boilerplate and truncation artifacts from a
    product title/label. Returns None if nothing usable is left."""
    if not text or not isinstance(text, str):
        return None

    cleaned = text.strip()
    cleaned = _LEADING_BUY_PATTERN.sub("", cleaned)
    cleaned = _LEADING_SITE_PREFIX_PATTERN.sub("", cleaned)
    cleaned = _ELLIPSIS_PATTERN.sub(" ", cleaned)
    cleaned = _TRAILING_SITE_SUFFIX_PATTERN.sub("", cleaned)
    cleaned = _TRAILING_RATING_PATTERN.sub("", cleaned)

    cleaned = " ".join(cleaned.split()).strip(" -|:")
    return cleaned or None
