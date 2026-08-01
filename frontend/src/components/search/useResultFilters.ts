import { useMemo, useState } from "react";
import type { PurchaseLink, SortBy } from "@/types";

export interface ResultFilters {
  query: string;
  storeType: "all" | "official" | "marketplace" | "quick_commerce";
  platforms: string[];
  pricedOnly: boolean;
  minPrice: string;
  maxPrice: string;
  sortBy: SortBy;
}

export const DEFAULT_FILTERS: ResultFilters = {
  query: "",
  storeType: "all",
  platforms: [],
  pricedOnly: false,
  minPrice: "",
  maxPrice: "",
  sortBy: "price_low",
};

function extractNumericPrice(price: string | null): number | null {
  if (!price) return null;
  const match = price.replace(/,/g, "").match(/[\d.]+/);
  if (!match) return null;
  const value = Number(match[0]);
  return Number.isFinite(value) ? value : null;
}

function isOfficial(product: PurchaseLink): boolean {
  return product.platform.toLowerCase().includes("official");
}

function applySort(results: PurchaseLink[], sortBy: SortBy): PurchaseLink[] {
  const withPrice = (p: PurchaseLink) => extractNumericPrice(p.price);
  const copy = [...results];

  switch (sortBy) {
    case "price_high":
      return copy.sort((a, b) => {
        const pa = withPrice(a);
        const pb = withPrice(b);
        if (pa === null) return 1;
        if (pb === null) return -1;
        return pb - pa;
      });
    case "rating":
      return copy.sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1));
    case "reviews":
      return copy.sort((a, b) => (b.review_count ?? -1) - (a.review_count ?? -1));
    case "platform":
      return copy.sort((a, b) => a.platform.localeCompare(b.platform));
    case "price_low":
    default:
      return copy.sort((a, b) => {
        const pa = withPrice(a);
        const pb = withPrice(b);
        if (pa === null) return 1;
        if (pb === null) return -1;
        return pa - pb;
      });
  }
}

export function useResultFilters(results: PurchaseLink[]) {
  const [filters, setFilters] = useState<ResultFilters>(DEFAULT_FILTERS);

  const availablePlatforms = useMemo(
    () => Array.from(new Set(results.map((r) => r.platform))).sort(),
    [results]
  );

  const filtered = useMemo(() => {
    const min = filters.minPrice ? Number(filters.minPrice) : null;
    const max = filters.maxPrice ? Number(filters.maxPrice) : null;
    const query = filters.query.trim().toLowerCase();

    const matches = results.filter((product) => {
      if (filters.storeType === "official" && !isOfficial(product)) return false;
      if (filters.storeType === "marketplace" && isOfficial(product)) return false;
      if (filters.storeType === "quick_commerce" && !product.is_quick_commerce) return false;

      if (filters.platforms.length > 0 && !filters.platforms.includes(product.platform)) {
        return false;
      }

      if (filters.pricedOnly && (product.price === null || product.price === undefined)) {
        return false;
      }

      const numericPrice = extractNumericPrice(product.price);
      if (min !== null && (numericPrice === null || numericPrice < min)) return false;
      if (max !== null && (numericPrice === null || numericPrice > max)) return false;

      if (query) {
        const haystack = `${product.title} ${product.platform}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }

      return true;
    });

    return applySort(matches, filters.sortBy);
  }, [results, filters]);

  const resetFilters = () => setFilters(DEFAULT_FILTERS);

  return { filters, setFilters, filtered, availablePlatforms, resetFilters };
}
