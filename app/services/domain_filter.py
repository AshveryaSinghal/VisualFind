"""
Anti-scam strategy: instead of trying to *classify* whether a link is a scam
(a hard, open-ended ML problem), we only ever surface links from a curated
allowlist of platforms we trust. Anything SerpApi returns from outside this
list is silently dropped. This is simpler, more defensible in an interview
("I chose allowlisting over classification because false negatives in fraud
detection are costly and hard to verify"), and never wrong in a way that
embarrasses the demo.

Extend this list as you add more platforms. Keep it to platforms with real
buyer protection / return policies.
"""

from urllib.parse import urlparse, quote_plus

TRUSTED_DOMAINS: dict[str, str] = {

    "amazon.in": "Amazon",
    "amazon.com": "Amazon",
    "flipkart.com": "Flipkart",
    "myntra.com": "Myntra",
    "nykaa.com": "Nykaa",
    "ajio.com": "Ajio",
    "tatacliq.com": "Tata CLiQ",
    "meesho.com": "Meesho",
    "purplle.com": "Purplle",
    "snapdeal.com": "Snapdeal",
    "reliancedigital.in": "Reliance Digital",
    "croma.com": "Croma",

    # Quick-commerce / instant-delivery platforms. Listings for these mostly
    # arrive via Google Shopping rather than Lens candidates, and product
    # pages are heavily JS-rendered and location-gated, so treat prices from
    # here as best-effort (see QUICK_COMMERCE_PLATFORMS below, which powers
    # the "fastest delivery" column).
    "blinkit.com": "Blinkit",
    "zeptonow.com": "Zepto",
}

# swiggy.com hosts both food delivery and Instamart (grocery). A plain
# domain match would mislabel every Swiggy food-delivery link as a
# quick-commerce grocery result, so this requires the "instamart" path
# segment too - see _match_path_scoped_platform.
_PATH_SCOPED_TRUSTED_DOMAINS: dict[str, tuple[str, str]] = {
    "swiggy.com": ("instamart", "Instamart"),
}

# Platforms tracked for the "fastest delivery" feature, with a static
# typical-delivery-window label. VisualFind has no live ETA source (that
# needs the shopper's pincode/location, which SerpApi's Google Shopping
# results don't carry) - these are well-known typical windows for the
# service, not a real-time promise, and the UI should present them as such.
#
# NOTE: Amazon Now / Amazon Fresh instant delivery is a feature inside the
# regular amazon.in app/site rather than a separate domain, so it can't be
# reliably distinguished from standard Amazon listings by URL alone and is
# intentionally left out of automatic detection here.
QUICK_COMMERCE_PLATFORMS: dict[str, str] = {
    "Blinkit": "10-15 min",
    "Zepto": "10-15 min",
    "Instamart": "15-30 min",
}

def is_quick_commerce(platform: str | None) -> bool:
    if not platform:
        return False
    return platform in QUICK_COMMERCE_PLATFORMS

def quick_commerce_delivery_estimate(platform: str | None) -> str | None:
    if not platform:
        return None
    return QUICK_COMMERCE_PLATFORMS.get(platform)

def _match_path_scoped_platform(netloc: str, path: str) -> str | None:
    for domain, (path_fragment, platform_name) in _PATH_SCOPED_TRUSTED_DOMAINS.items():
        if netloc == domain or netloc.endswith("." + domain):
            if path_fragment in path.lower():
                return platform_name
    return None

def match_trusted_platform(url: str) -> str | None:
    """Returns the display platform name if the URL's domain is on the allowlist, else None.

    Matches the netloc against each allowlisted domain by exact match or as a
    real subdomain (netloc == domain or netloc.endswith("." + domain)) - not
    substring containment. A naive `domain_fragment in netloc` check would
    incorrectly trust a lookalike host like "amazon.com.evil-scam.ru", since
    "amazon.com" is a substring of that netloc even though it isn't the
    actual domain being visited.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
    except Exception:
        return None
    if not netloc:
        return None

    netloc = netloc.split(":")[0]

    for domain, platform_name in TRUSTED_DOMAINS.items():
        if netloc == domain or netloc.endswith("." + domain):
            return platform_name

    return _match_path_scoped_platform(netloc, parsed.path or "")

def list_trusted_platforms() -> list[str]:
    """Sorted list of unique display platform names. Adding a new platform is a
    one-line addition to TRUSTED_DOMAINS above - nothing else needs to change."""
    path_scoped_names = {name for _, name in _PATH_SCOPED_TRUSTED_DOMAINS.values()}
    return sorted(set(TRUSTED_DOMAINS.values()) | path_scoped_names)

# SerpApi's plain Google Shopping engine (google_shopping_search /
# extract_shopping_offers) returns each result's `link`/`product_link` as a
# Google-hosted page (google.com/shopping/product/<id>), not the retailer's
# own URL - getting the real retailer URL requires a *second* API call per
# product (the Google Immersive Product engine). That means
# match_trusted_platform() above almost never matches a Google-Shopping
# offer by URL alone, even though it's really from Amazon/Flipkart/etc.
#
# The one field that reliably names the real merchant in that case is
# `source` (e.g. "Amazon.in", "Flipkart.com", "Nykaa"). This is a
# keyword-substring fallback matcher for that field, used only when the URL
# itself didn't match the allowlist.
_SOURCE_NAME_KEYWORDS: dict[str, str] = {
    "amazon": "Amazon",
    "flipkart": "Flipkart",
    "myntra": "Myntra",
    "nykaa": "Nykaa",
    "ajio": "Ajio",
    "tata cliq": "Tata CLiQ",
    "tatacliq": "Tata CLiQ",
    "meesho": "Meesho",
    "purplle": "Purplle",
    "snapdeal": "Snapdeal",
    "reliance digital": "Reliance Digital",
    "reliancedigital": "Reliance Digital",
    "croma": "Croma",
    "blinkit": "Blinkit",
    "zepto": "Zepto",
    "instamart": "Instamart",
}

def match_trusted_platform_by_source(source: str | None) -> str | None:
    """Fallback for offers whose link isn't on our domain allowlist (see the
    comment above) but whose `source` field names a trusted retailer directly."""
    if not source:
        return None
    normalized = source.strip().lower()
    for keyword, platform_name in _SOURCE_NAME_KEYWORDS.items():
        if keyword in normalized:
            return platform_name
    return None

# When an offer was only matched via source name (i.e. its actual link is a
# Google page, not the retailer's), this builds a real, working search-results
# link on the correct platform instead - so the user still lands on Amazon /
# Flipkart / etc. rather than an intermediary Google page. Best-effort: it's
# a search results page for the product name, not guaranteed to be the exact
# listing SerpApi priced.
_PLATFORM_SEARCH_URL_TEMPLATES: dict[str, str] = {
    "Amazon": "https://www.amazon.in/s?k={query}",
    "Flipkart": "https://www.flipkart.com/search?q={query}",
    "Myntra": "https://www.myntra.com/{slug}?rawQuery={query}",
    "Nykaa": "https://www.nykaa.com/search/result/?q={query}",
    "Ajio": "https://www.ajio.com/search/?text={query}",
    "Tata CLiQ": "https://www.tatacliq.com/search/?searchCategory=all&text={query}",
    "Meesho": "https://www.meesho.com/search?q={query}",
    "Purplle": "https://www.purplle.com/search?q={query}",
    "Snapdeal": "https://www.snapdeal.com/search?keyword={query}",
    "Reliance Digital": "https://www.reliancedigital.in/search?q={query}",
    "Croma": "https://www.croma.com/searchB?q={query}",
    "Blinkit": "https://blinkit.com/s/?q={query}",
    "Zepto": "https://www.zeptonow.com/search?query={query}",
    "Instamart": "https://www.swiggy.com/instamart/search?custom_back=true&query={query}",
}

def build_platform_search_link(platform: str, query: str) -> str | None:
    """Direct search-results URL on `platform` for `query`, or None if we
    don't have a template for that platform."""
    template = _PLATFORM_SEARCH_URL_TEMPLATES.get(platform)
    if not template or not query:
        return None
    encoded = quote_plus(query.strip())
    slug = quote_plus(query.strip().lower().replace(" ", "-"))
    return template.format(query=encoded, slug=slug)

SELLER_CREDIBILITY: dict[str, float] = {
    "Amazon": 1.0,
    "Flipkart": 0.95,
    "Tata CLiQ": 0.9,
    "Croma": 0.88,
    "Reliance Digital": 0.88,
    "Myntra": 0.85,
    "Ajio": 0.8,
    "Nykaa": 0.85,
    "Purplle": 0.75,
    "Snapdeal": 0.7,
    "Meesho": 0.65,
    "Blinkit": 0.8,
    "Zepto": 0.8,
    "Instamart": 0.8,
}
_DEFAULT_CREDIBILITY = 0.75
_OFFICIAL_STORE_BONUS = 0.15

def seller_credibility(platform: str | None) -> float:
    """0.0-1.0 relative seller-credibility score for the Best Deal engine.

    An "official <brand> store" result (see brand_resolution/) gets a bonus on
    top of its base platform weight, capped at 1.0, since buying directly from
    the brand is the strongest guarantee of authenticity."""
    if not platform:
        return _DEFAULT_CREDIBILITY

    base = _DEFAULT_CREDIBILITY
    for known_name, weight in SELLER_CREDIBILITY.items():
        if known_name.lower() in platform.lower():
            base = weight
            break

    if "official" in platform.lower():
        base = min(1.0, base + _OFFICIAL_STORE_BONUS)

    return base
