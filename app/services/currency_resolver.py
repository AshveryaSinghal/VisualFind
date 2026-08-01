"""
CurrencyResolverService - the single, centralized place that decides what
ISO-4217 currency code (if any) applies to a price we found somewhere on
the internet.

Every other service (price_extraction/normalization.py, price_service.py,
brand_resolution/official_site_search.py, ...) used to each carry their own
copy of a currency-symbol table and their own ad-hoc domain guess. That
duplication is exactly how a "reasonable-looking" `.com -> USD` heuristic
snuck in and started mislabeling Nykaa (nykaa.com) as USD even though
Nykaa is an Indian rupee storefront. This module replaces every one of
those copies.

Resolution order (first tier that produces a confident answer wins):
  1. Currency extracted together with the price itself - an explicit
     currency field SerpApi/Lens returned alongside the price, or a
     currency symbol/code embedded directly in the price string
     (e.g. "₹1,299", "$19.99").
  2. JSON-LD Product/Offer schema `priceCurrency`.
  3. Other structured page metadata - schema.org microdata
     (`itemprop="priceCurrency"`), generic `<meta name="price">`-style
     tags, or inline-script JSON price blobs.
  4. OpenGraph / product:* meta tags (`og:price:currency`,
     `product:price:currency`).
  5. Platform mapping - the trusted-platform display name (e.g. "Nykaa",
     see domain_filter.TRUSTED_DOMAINS) mapped to that platform's known
     operating currency.
  6. Domain mapping - the URL's registrable domain mapped to a known
     operating currency (e.g. nykaa.com -> INR, amazon.co.uk -> GBP).

If none of the six tiers resolves a currency, `resolve()` returns None.
It never fabricates or defaults to a currency (in particular, never USD)
- "we don't know the currency" has to stay representable, otherwise a
rupee price silently gets mislabeled as dollars (or vice versa).
"""

import re
from urllib.parse import urlparse

_ISO_CODES = {"INR", "USD", "EUR", "GBP"}

_SYMBOL_OR_ALIAS_TO_ISO = {
    "₹": "INR",
    "rs": "INR",
    "rs.": "INR",
    "inr": "INR",
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
}

_SYMBOL_PATTERN = re.compile(r"[₹$€£]")

_PLATFORM_CURRENCY = {
    "flipkart": "INR",
    "myntra": "INR",
    "nykaa": "INR",
    "ajio": "INR",
    "tata cliq": "INR",
    "meesho": "INR",
    "purplle": "INR",
    "snapdeal": "INR",
    "reliance digital": "INR",
    "croma": "INR",
}

_DOMAIN_CURRENCY = {

    "amazon.in": "INR",
    "amazon.com": "USD",
    "amazon.co.uk": "GBP",
    "amazon.de": "EUR",

    "flipkart.com": "INR",
    "myntra.com": "INR",
    "nykaa.com": "INR",
    "nykaacosmetics.com": "INR",
    "ajio.com": "INR",
    "tatacliq.com": "INR",
    "meesho.com": "INR",
    "purplle.com": "INR",
    "snapdeal.com": "INR",
    "reliancedigital.in": "INR",
    "croma.com": "INR",

    "plumgoodness.com": "INR",
    "mamaearth.in": "INR",
    "sugarcosmetics.com": "INR",
    "lakmeindia.com": "INR",
    "biotique.com": "INR",
    "himalayawellness.in": "INR",
    "wowskinscience.com": "INR",
    "themancompany.com": "INR",
    "mcaffeine.com": "INR",
    "beminimalist.co": "INR",
    "dotandkey.com": "INR",
    "forestessentialsindia.com": "INR",
    "khadinatural.com": "INR",
    "vlccpersonalcare.com": "INR",
    "nivea.in": "INR",
    "thebodyshop.in": "INR",
    "garnier.in": "INR",
    "adidas.co.in": "INR",
    "in.puma.com": "INR",
    "levi.in": "INR",
    "woodlandworldwide.com": "INR",
    "bata.in": "INR",
    "allensolly.com": "INR",
    "vanheusenindia.com": "INR",
    "fabindia.com": "INR",
    "biba.in": "INR",
    "wforwoman.com": "INR",
    "sony.co.in": "INR",
    "boat-lifestyle.com": "INR",
    "gonoise.com": "INR",
    "oneplus.in": "INR",
    "philips.co.in": "INR",
    "ttkprestige.com": "INR",
    "havells.com": "INR",
    "bajajelectricals.com": "INR",
    "miltonindia.com": "INR",
    "celloworld.com": "INR",
    "pigeonappliances.com": "INR",

    "maybelline.com": "USD",
    "lorealparisusa.com": "USD",
    "dove.com": "USD",
    "nike.com": "USD",
    "hm.com": "USD",
    "zara.com": "USD",
    "apple.com": "USD",
}

class CurrencyResolverService:
    """
    Stateless resolver - safe to use as a shared singleton (see
    `currency_resolver` below) or instantiate fresh, doesn't matter.

    This is the *only* place in the codebase that should know about
    currency symbols, platform-currency mappings, or domain-currency
    mappings. Everywhere else should call `resolve()`.
    """

    def resolve(
        self,
        *,
        price_currency: str | None = None,
        json_ld_currency: str | None = None,
        structured_metadata_currency: str | None = None,
        opengraph_currency: str | None = None,
        price_text: str | None = None,
        platform: str | None = None,
        url: str | None = None,
    ) -> str | None:
        """
        Resolves a currency using the six-tier priority order described in
        this module's docstring. Returns None - never a fabricated default
        - if nothing resolves.

        Every argument is optional; callers pass whatever signals they
        actually have for the price in question. `price_text` covers the
        common case of a currency symbol embedded in the raw price string
        itself (e.g. "₹1,299") when no separate currency field was given.
        """

        for raw in (
            price_currency,
            json_ld_currency,
            structured_metadata_currency,
            opengraph_currency,
        ):
            code = self._normalize_explicit(raw)
            if code:
                return code

        if price_text:
            code = self._detect_symbol(price_text)
            if code:
                return code

        if platform:
            code = _PLATFORM_CURRENCY.get(" ".join(platform.strip().lower().split()))
            if code:
                return code

        if url:
            code = self._domain_lookup(url)
            if code:
                return code

        return None

    @staticmethod
    def _normalize_explicit(raw: str | None) -> str | None:
        if not raw:
            return None
        key = raw.strip().lower()
        if key in _SYMBOL_OR_ALIAS_TO_ISO:
            return _SYMBOL_OR_ALIAS_TO_ISO[key]
        upper = raw.strip().upper()
        if upper in _ISO_CODES:
            return upper
        return None

    @staticmethod
    def _detect_symbol(text: str) -> str | None:
        match = _SYMBOL_PATTERN.search(text)
        if match:
            return _SYMBOL_OR_ALIAS_TO_ISO.get(match.group(0))
        return None

    @staticmethod
    def _domain_lookup(url: str) -> str | None:
        try:
            netloc = urlparse(url).netloc.lower()
        except Exception:
            return None
        if not netloc:
            return None

        best_match: tuple[str, str] | None = None
        for domain, code in _DOMAIN_CURRENCY.items():
            if netloc == domain or netloc.endswith("." + domain):
                if best_match is None or len(domain) > len(best_match[0]):
                    best_match = (domain, code)
        if best_match:
            return best_match[1]

        if netloc.endswith(".in") or netloc == "in":
            return "INR"

        return None

currency_resolver = CurrencyResolverService()
