"""
Tier 3 - Headless browser rendering.

Last resort: for pages that expose no structured data at all and build the
price into the DOM client-side (React/Vue storefronts that hydrate after
load), render the page with a real browser engine and read the visible
price text out of the rendered DOM.

This is the slowest and most fragile tier, so it only runs when Tiers 1-2
found nothing. It's also the one tier with a genuine optional dependency:
Playwright needs a browser binary installed (`playwright install chromium`)
that isn't always available in every deployment environment (e.g. locked-down
sandboxes with no access to the browser-download CDN). Rather than make that
a hard dependency of the whole app, this strategy lazy-imports Playwright and
degrades to a clean "unavailable" failure if it's missing - the pipeline
falls through to returning `price=None` for that product, it never crashes.

To enable this tier in a deployment that has network access for the browser
download: `pip install playwright && playwright install chromium`.
"""

import re

from app.config import settings
from app.services.price_extraction.strategies.base import ExtractionStrategy
from app.services.price_extraction.types import PriceCandidate, StrategyOutcome
from app.services.price_extraction.validation import infer_role_from_text

_PRICE_SELECTORS = [
    "[data-testid*='price' i]",
    "[class*='selling-price' i]",
    "[class*='sale-price' i]",
    "[class*='offer-price' i]",
    "[class*='final-price' i]",
    "[itemprop='price']",
    "[class*='price' i]",
    "[id*='price' i]",
]

_PRICE_TEXT_PATTERN = re.compile(r"[₹$€£]\s?[\d,]+(?:\.\d+)?|[\d,]{2,}(?:\.\d+)?")

class HeadlessBrowserStrategy(ExtractionStrategy):
    name = "headless_browser"

    def _run(self, url: str | None = None, **_) -> StrategyOutcome:
        if not settings.enable_headless_browser_fallback:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="disabled",
                success=False,
                candidates=[],
                error="headless browser fallback disabled via config",
            )
        if not url:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="none",
                success=False,
                candidates=[],
                error="no url provided",
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="unavailable",
                success=False,
                candidates=[],
                error="playwright is not installed in this environment",
            )

        candidates: list[PriceCandidate] = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=(
                        "Mozilla/5.0 (compatible; VisualFindBot/1.0; +https://example.com/bot)"
                    ))
                    page.goto(url, timeout=int(settings.headless_browser_timeout_seconds * 1000))

                    page.wait_for_load_state("networkidle", timeout=int(
                        settings.headless_browser_timeout_seconds * 1000
                    ))

                    candidates = self._extract_from_rendered_page(page)
                finally:
                    browser.close()
        except Exception as e:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="rendered_dom",
                success=False,
                candidates=[],
                error=f"render/extract failed: {e}",
            )

        if not candidates:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="rendered_dom",
                success=False,
                candidates=[],
                error="no price text found in rendered DOM",
            )

        return StrategyOutcome(
            strategy_name=self.name,
            extraction_method="rendered_dom",
            success=True,
            candidates=candidates,
        )

    def _extract_from_rendered_page(self, page) -> list[PriceCandidate]:
        found: list[PriceCandidate] = []
        seen_texts: set[str] = set()

        for selector in _PRICE_SELECTORS:
            try:
                elements = page.query_selector_all(selector)
            except Exception:
                continue

            for el in elements[:10]:
                try:
                    text = (el.inner_text() or "").strip()
                except Exception:
                    continue

                if not text or text in seen_texts:
                    continue
                match = _PRICE_TEXT_PATTERN.search(text)
                if not match:
                    continue

                seen_texts.add(text)
                class_attr = ""
                try:
                    class_attr = el.get_attribute("class") or ""
                except Exception:
                    pass

                role = infer_role_from_text(class_attr, text)
                found.append(
                    PriceCandidate(
                        raw_price=match.group(0),
                        raw_currency=None,
                        role=role,
                        label=f"rendered_dom.{selector}",
                        context=text[:80],
                    )
                )

                if len(found) >= 15:
                    return found

        return found
