import { apiClient } from "@/api/client";
import type { ProductAnalyticsQuery, ProductAnalyticsResponse } from "@/types";

export async function getProductAnalytics(
  query: ProductAnalyticsQuery
): Promise<ProductAnalyticsResponse> {
  const { data } = await apiClient.get<ProductAnalyticsResponse>("/api/products/analytics", {
    params: {
      title: query.title,
      platform: query.platform ?? undefined,
      price: query.price ?? undefined,
      currency: query.currency ?? undefined,
      rating: query.rating ?? undefined,
      review_count: query.review_count ?? undefined,
      thumbnail: query.thumbnail ?? undefined,
      link: query.link ?? undefined,
    },
  });
  return data;
}
