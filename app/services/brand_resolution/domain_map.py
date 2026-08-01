"""
Local brand -> official-domain mapping.

This is Tier 1 of BrandDomainResolver (see resolver.py): the cheapest,
fastest, most reliable strategy - no network call at all - so it's tried
before anything else. Extending brand coverage later is a one-line addition
here; nothing else in the pipeline needs to change.

Keys are lowercase, whitespace-collapsed brand names. Keep this list to
brands whose official e-commerce domain is well-known and stable.
"""

BRAND_DOMAIN_MAP: dict[str, str] = {

    "plum": "plumgoodness.com",
    "mamaearth": "mamaearth.in",
    "sugar cosmetics": "sugarcosmetics.com",
    "nykaa cosmetics": "nykaacosmetics.com",
    "lakme": "lakmeindia.com",
    "biotique": "biotique.com",
    "himalaya": "himalayawellness.in",
    "wow skin science": "wowskinscience.com",
    "the man company": "themancompany.com",
    "mcaffeine": "mcaffeine.com",
    "minimalist": "beminimalist.co",
    "dot & key": "dotandkey.com",
    "forest essentials": "forestessentialsindia.com",
    "khadi natural": "khadinatural.com",
    "vlcc": "vlccpersonalcare.com",

    "maybelline": "maybelline.com",
    "loreal": "lorealparisusa.com",
    "nivea": "nivea.in",
    "dove": "dove.com",
    "the body shop": "thebodyshop.in",
    "garnier": "garnier.in",

    "nike": "nike.com",
    "adidas": "adidas.co.in",
    "puma": "in.puma.com",
    "levis": "levi.in",
    "h&m": "hm.com",
    "zara": "zara.com",
    "woodland": "woodlandworldwide.com",
    "bata": "bata.in",
    "allen solly": "allensolly.com",
    "van heusen": "vanheusenindia.com",
    "fabindia": "fabindia.com",
    "biba": "biba.in",
    "w for woman": "wforwoman.com",

    "samsung": "samsung.com",
    "apple": "apple.com",
    "sony": "sony.co.in",
    "boat": "boat-lifestyle.com",
    "noise": "gonoise.com",
    "mi": "mi.com",
    "xiaomi": "mi.com",
    "oneplus": "oneplus.in",
    "philips": "philips.co.in",
    "prestige": "ttkprestige.com",
    "havells": "havells.com",
    "bajaj": "bajajelectricals.com",

    "milton": "miltonindia.com",
    "cello": "celloworld.com",
    "pigeon": "pigeonappliances.com",
}

NON_OFFICIAL_DOMAIN_FRAGMENTS: tuple[str, ...] = (
    "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com",
    "linkedin.com", "pinterest.com", "wikipedia.org", "reddit.com",
    "quora.com", "indiamart.com", "justdial.com", "tradeindia.com",
    "google.com", "play.google.com", "apps.apple.com",
)

def lookup_domain(brand_name: str) -> str | None:
    """Exact-then-fuzzy lookup against the static map. Fuzzy match handles
    e.g. brand detected as 'Plum' matching the map's 'plum', or a detected
    'Plum Goodness' matching 'plum'."""
    if not brand_name:
        return None
    key = " ".join(brand_name.lower().split())

    if key in BRAND_DOMAIN_MAP:
        return BRAND_DOMAIN_MAP[key]

    for map_key, domain in BRAND_DOMAIN_MAP.items():
        if map_key in key or key in map_key:
            return domain

    return None
