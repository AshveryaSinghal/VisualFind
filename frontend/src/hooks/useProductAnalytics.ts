import { useQuery } from "@tanstack/react-query";
import { getProductAnalytics } from "@/services/productService";
import { queryKeys } from "@/hooks/queryKeys";
import type { ProductAnalyticsQuery } from "@/types";

export function useProductAnalytics(query: ProductAnalyticsQuery | null) {
  return useQuery({
    queryKey: query
      ? queryKeys.productAnalytics(query.title, query.platform)
      : ["productAnalytics", "disabled"],
    queryFn: () => getProductAnalytics(query as ProductAnalyticsQuery),
    enabled: !!query?.title,
    staleTime: 60_000,
    retry: 1,
  });
}
