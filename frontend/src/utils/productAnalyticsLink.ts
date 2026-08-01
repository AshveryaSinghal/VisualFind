import type { ProductAnalyticsQuery, PurchaseLink } from "@/types";

export function buildProductAnalyticsSearch(product: PurchaseLink): string {
  const params = new URLSearchParams();
  params.set("title", product.title);

  if (product.platform) params.set("platform", product.platform);
  if (product.currency) params.set("currency", product.currency);
  if (product.thumbnail) params.set("thumbnail", product.thumbnail);
  if (product.link) params.set("link", product.link);

  const numericPrice = product.price !== null && product.price !== undefined ? Number(product.price) : NaN;
  if (Number.isFinite(numericPrice)) params.set("price", String(numericPrice));

  if (product.rating !== null && product.rating !== undefined) {
    params.set("rating", String(product.rating));
  }
  if (product.review_count !== null && product.review_count !== undefined) {
    params.set("review_count", String(product.review_count));
  }

  return params.toString();
}

export function parseProductAnalyticsSearch(searchParams: URLSearchParams): ProductAnalyticsQuery | null {
  const title = searchParams.get("title");
  if (!title) return null;

  const priceRaw = searchParams.get("price");
  const ratingRaw = searchParams.get("rating");
  const reviewCountRaw = searchParams.get("review_count");

  return {
    title,
    platform: searchParams.get("platform"),
    currency: searchParams.get("currency"),
    thumbnail: searchParams.get("thumbnail"),
    link: searchParams.get("link"),
    price: priceRaw !== null && Number.isFinite(Number(priceRaw)) ? Number(priceRaw) : null,
    rating: ratingRaw !== null && Number.isFinite(Number(ratingRaw)) ? Number(ratingRaw) : null,
    review_count:
      reviewCountRaw !== null && Number.isFinite(Number(reviewCountRaw)) ? Number(reviewCountRaw) : null,
  };
}
