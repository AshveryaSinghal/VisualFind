import { describe, expect, it } from "vitest";
import { buildProductAnalyticsSearch, parseProductAnalyticsSearch } from "@/utils/productAnalyticsLink";
import type { PurchaseLink } from "@/types";

const product: PurchaseLink = {
  platform: "Flipkart",
  title: "Wireless Headphones XR-500",
  brand: "XR-500",
  price: "2499",
  currency: "INR",
  link: "https://flipkart.com/xr-500",
  source_domain: "flipkart.com",
  thumbnail: "https://flipkart.com/thumb.jpg",
  rating: 4.3,
  review_count: 1200,
  price_source: "google_shopping",
  extraction_method: null,
  confidence_score: 0.92,
  is_best_deal: true,
  savings: 300,
  best_deal_reason: "Chosen for its lowest price among trusted sellers.",
  is_quick_commerce: false,
  delivery_estimate: null,
};

describe("buildProductAnalyticsSearch / parseProductAnalyticsSearch round trip", () => {
  it("round-trips every field through the query string", () => {
    const search = buildProductAnalyticsSearch(product);
    const parsed = parseProductAnalyticsSearch(new URLSearchParams(search));

    expect(parsed).toEqual({
      title: product.title,
      platform: product.platform,
      currency: product.currency,
      thumbnail: product.thumbnail,
      link: product.link,
      price: 2499,
      rating: 4.3,
      review_count: 1200,
    });
  });

  it("omits optional fields that are missing rather than writing empty params", () => {
    const search = buildProductAnalyticsSearch({ ...product, platform: "", thumbnail: null });
    const params = new URLSearchParams(search);

    expect(params.has("platform")).toBe(false);
    expect(params.has("thumbnail")).toBe(false);
  });

  it("drops a non-numeric price instead of encoding NaN", () => {
    const search = buildProductAnalyticsSearch({ ...product, price: "Contact seller" });
    const params = new URLSearchParams(search);

    expect(params.has("price")).toBe(false);
  });

  it("returns null when the required title param is missing", () => {
    const parsed = parseProductAnalyticsSearch(new URLSearchParams("platform=Flipkart"));
    expect(parsed).toBeNull();
  });

  it("treats a non-numeric rating/review_count param as null rather than NaN", () => {
    const parsed = parseProductAnalyticsSearch(
      new URLSearchParams("title=Test+Product&rating=not-a-number&review_count=also-bad")
    );

    expect(parsed).toEqual({
      title: "Test Product",
      platform: null,
      currency: null,
      thumbnail: null,
      link: null,
      price: null,
      rating: null,
      review_count: null,
    });
  });
});
