import { useMemo, useState } from "react";
import type { HistoryItem } from "@/types";
import { useDebounce } from "@/hooks/useDebounce";

export function useHistoryFilters(items: HistoryItem[]) {
  const [query, setQuery] = useState("");
  const [officialOnly, setOfficialOnly] = useState(false);
  const debouncedQuery = useDebounce(query, 250);

  const filtered = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    return items.filter((item) => {
      if (officialOnly && !item.official_domain) return false;
      if (!q) return true;
      const haystack = `${item.best_guess_label ?? ""} ${item.product_query ?? ""} ${
        item.detected_brand ?? ""
      } ${item.best_deal_platform ?? ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [items, debouncedQuery, officialOnly]);

  return { query, setQuery, officialOnly, setOfficialOnly, filtered };
}
