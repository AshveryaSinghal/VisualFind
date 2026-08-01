import { AnimatePresence } from "framer-motion";
import type { PurchaseLink } from "@/types";
import { ProductCard } from "@/components/search/ProductCard";
import { EmptyState } from "@/components/common/EmptyState";
import { SearchX } from "lucide-react";

interface ResultsGridProps {
  results: PurchaseLink[];
  emptyMessage?: string;
  /** Tab-local object URL for the searched photo, used only as a display
   * fallback for result cards missing a product image. */
  fallbackImage?: string | null;
  /** Forwarded to ProductCard - forces the Compare/Analytics buttons to
   * icon-only. Use this wherever the grid renders in a narrower column
   * (e.g. the AI assistant) instead of relying on the card squeezing
   * itself down and clipping its labels. */
  compactActions?: boolean;
}

export function ResultsGrid({ results, emptyMessage, fallbackImage, compactActions }: ResultsGridProps) {
  if (results.length === 0) {
    return (
      <EmptyState
        icon={SearchX}
        title="No products match your filters"
        description={
          emptyMessage ?? "Try widening your filters or searching a different term within results."
        }
      />
    );
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(18rem,1fr))] gap-5">
      <AnimatePresence initial={false}>
        {results.map((product, index) => (
          <ProductCard
            key={`${product.link}-${index}`}
            product={product}
            index={index}
            fallbackImage={fallbackImage}
            compactActions={compactActions}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
