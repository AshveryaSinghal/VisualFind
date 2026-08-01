import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import type { SavedProduct } from "@/types";
import { useSavedProducts, useSaveProduct, useUnsaveProduct } from "@/hooks/usePersonalization";

/** The minimal shape needed to save/toggle a product - deliberately looser
 * than PurchaseLink so callers that don't have a full search result on hand
 * (e.g. the Product Analytics page, working from URL params) can use this
 * too, as long as they have a title. */
export interface SavableProduct {
  title: string;
  platform?: string | null;
  price?: number | string | null;
  currency?: string | null;
  thumbnail?: string | null;
  link?: string | null;
  rating?: number | null;
  review_count?: number | null;
}

interface SavedProductsContextValue {
  items: SavedProduct[];
  isLoading: boolean;
  isSaved: (product: { title: string }) => boolean;
  toggle: (product: SavableProduct) => void;
  isToggling: boolean;
}

const SavedProductsContext = createContext<SavedProductsContextValue | undefined>(undefined);

function normalizeName(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, " ");
}

export function SavedProductsProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = useSavedProducts();
  const saveMutation = useSaveProduct();
  const unsaveMutation = useUnsaveProduct();

  const items = useMemo(() => data ?? [], [data]);

  const savedByName = useMemo(() => {
    const map = new Map<string, SavedProduct>();
    for (const item of items) {
      map.set(normalizeName(item.product_name), item);
    }
    return map;
  }, [items]);

  const isSaved = useCallback(
    (product: { title: string }) => savedByName.has(normalizeName(product.title)),
    [savedByName]
  );

  const toggle = useCallback(
    (product: SavableProduct) => {
      const existing = savedByName.get(normalizeName(product.title));
      if (existing) {
        unsaveMutation.mutate(existing.id);
        return;
      }

      const numericPrice = product.price !== null && product.price !== undefined ? Number(product.price) : null;

      saveMutation.mutate({
        product_name: product.title,
        platform: product.platform ?? undefined,
        price: Number.isFinite(numericPrice) ? numericPrice : undefined,
        currency: product.currency ?? undefined,
        thumbnail: product.thumbnail ?? undefined,
        link: product.link ?? undefined,
        rating: product.rating ?? undefined,
        review_count: product.review_count ?? undefined,
      });
    },
    [savedByName, saveMutation, unsaveMutation]
  );

  const value = useMemo<SavedProductsContextValue>(
    () => ({
      items,
      isLoading,
      isSaved,
      toggle,
      isToggling: saveMutation.isPending || unsaveMutation.isPending,
    }),
    [items, isLoading, isSaved, toggle, saveMutation.isPending, unsaveMutation.isPending]
  );

  return <SavedProductsContext.Provider value={value}>{children}</SavedProductsContext.Provider>;
}

export function useSavedProductsContext(): SavedProductsContextValue {
  const ctx = useContext(SavedProductsContext);
  if (!ctx) throw new Error("useSavedProductsContext must be used within a SavedProductsProvider");
  return ctx;
}
