import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { PurchaseLink } from "@/types";

export const MAX_COMPARE_ITEMS = 4;

interface CompareContextValue {
  items: PurchaseLink[];
  isSelected: (product: PurchaseLink) => boolean;
  toggle: (product: PurchaseLink) => void;
  remove: (product: PurchaseLink) => void;
  clear: () => void;
  isOpen: boolean;
  open: () => void;
  close: () => void;
  isFull: boolean;
}

const CompareContext = createContext<CompareContextValue | undefined>(undefined);

function keyOf(product: PurchaseLink): string {
  return `${product.platform}::${product.link}`;
}

export function CompareProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState<Map<string, PurchaseLink>>(new Map());
  const [isOpen, setIsOpen] = useState(false);

  const isSelected = useCallback(
    (product: PurchaseLink) => selected.has(keyOf(product)),
    [selected]
  );

  const toggle = useCallback((product: PurchaseLink) => {
    setSelected((prev) => {
      const next = new Map(prev);
      const key = keyOf(product);
      if (next.has(key)) {
        next.delete(key);
      } else {
        if (next.size >= MAX_COMPARE_ITEMS) return prev;
        next.set(key, product);
      }
      return next;
    });
  }, []);

  const remove = useCallback((product: PurchaseLink) => {
    setSelected((prev) => {
      const next = new Map(prev);
      next.delete(keyOf(product));
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setSelected(new Map());
    setIsOpen(false);
  }, []);

  const items = useMemo(() => Array.from(selected.values()), [selected]);

  const value = useMemo<CompareContextValue>(
    () => ({
      items,
      isSelected,
      toggle,
      remove,
      clear,
      isOpen,
      open: () => setIsOpen(true),
      close: () => setIsOpen(false),
      isFull: items.length >= MAX_COMPARE_ITEMS,
    }),
    [items, isSelected, toggle, remove, clear, isOpen]
  );

  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export function useCompare(): CompareContextValue {
  const ctx = useContext(CompareContext);
  if (!ctx) throw new Error("useCompare must be used within a CompareProvider");
  return ctx;
}
