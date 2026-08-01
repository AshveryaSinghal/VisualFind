import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  ExternalLink,
  Star,
  ShieldCheck,
  BadgeCheck,
  Sparkles,
  PackageCheck,
  PackageX,
  Wand2,
} from "lucide-react";
import { useCompare } from "@/context/CompareContext";
import { formatPrice, formatSavings } from "@/utils/format";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { SmartCompareDialog } from "@/components/compare/SmartCompareDialog";

const ROWS: {
  label: string;
}[] = [
  { label: "Price" },
  { label: "Rating" },
  { label: "Reviews" },
  { label: "Availability" },
  { label: "Seller" },
  { label: "Official store" },
  { label: "Price confidence" },
];

export function CompareDialog() {
  const { items, isOpen, close, remove } = useCompare();
  const [smartCompareOpen, setSmartCompareOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.addEventListener("keydown", handleEscape);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "";
    };
  }, [isOpen, close]);

  const bestDealKey = items.find((item) => item.is_best_deal)
    ? `${items.find((item) => item.is_best_deal)!.platform}::${
        items.find((item) => item.is_best_deal)!.link
      }`
    : null;

  return (
    <>
      {createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[95] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={close}
            className="absolute inset-0 bg-background/85 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 12 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
            className="relative z-[96] flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <div>
                <h2 className="text-lg font-semibold text-foreground">Compare products</h2>
                <p className="text-sm text-muted-foreground">
                  Side-by-side view of everything VisualFind found for these listings.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {items.length === 2 && (
                  <Button size="sm" onClick={() => setSmartCompareOpen(true)}>
                    <Wand2 className="h-3.5 w-3.5" />
                    Compare with AI
                  </Button>
                )}
                <button
                  onClick={close}
                  aria-label="Close comparison"
                  className="rounded-md p-2 text-muted-foreground transition hover:bg-accent hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="overflow-auto">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 w-40 bg-card p-4 text-left align-bottom text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Product
                    </th>
                    {items.map((item) => {
                      const key = `${item.platform}::${item.link}`;
                      const isBest = key === bestDealKey;
                      return (
                        <th
                          key={key}
                          className={cn(
                            "min-w-[15rem] border-l border-border p-4 text-left align-top",
                            isBest && "bg-success/5"
                          )}
                        >
                          <div className="space-y-2">
                            <button
                              onClick={() => remove(item)}
                              className="flex items-center gap-1 text-xs text-muted-foreground transition hover:text-destructive"
                            >
                              <X className="h-3 w-3" /> Remove
                            </button>
                            <div className="flex h-24 w-full items-center justify-center overflow-hidden rounded-lg bg-muted">
                              {item.thumbnail ? (
                                <img
                                  src={item.thumbnail}
                                  alt={item.title}
                                  className="h-full w-full object-contain p-2"
                                />
                              ) : (
                                <Sparkles className="h-6 w-6 text-muted-foreground" />
                              )}
                            </div>
                            <p className="line-clamp-2 text-sm font-medium leading-snug text-foreground">
                              {item.title}
                            </p>
                            {isBest && (
                              <Badge variant="success">
                                <BadgeCheck className="h-3 w-3" />
                                AI recommended
                              </Badge>
                            )}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((row) => (
                    <tr key={row.label} className="border-t border-border">
                      <th className="sticky left-0 z-10 w-40 bg-card p-4 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {row.label}
                      </th>
                      {items.map((item) => {
                        const key = `${item.platform}::${item.link}`;
                        return (
                          <td key={key} className="border-l border-border p-4 align-middle">
                            {renderCell(row.label, item)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  <tr className="border-t border-border">
                    <th className="sticky left-0 z-10 w-40 bg-card p-4" />
                    {items.map((item) => {
                      const key = `${item.platform}::${item.link}`;
                      return (
                        <td key={key} className="border-l border-border p-4">
                          <a
                            href={item.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={cn(buttonVariants({ size: "sm" }), "w-full")}
                          >
                            View product
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        </td>
                      );
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
        document.body
      )}
      <SmartCompareDialog
        open={smartCompareOpen}
        onClose={() => setSmartCompareOpen(false)}
        productA={items[0] ?? null}
        productB={items[1] ?? null}
      />
    </>
  );
}

function renderCell(label: string, item: import("@/types").PurchaseLink) {
  switch (label) {
    case "Price": {
      const savings = formatSavings(item.savings, item.currency);
      return (
        <div className="space-y-0.5">
          <div className="text-base font-semibold text-foreground">
            {formatPrice(item.price, item.currency)}
          </div>
          {savings && <div className="text-xs font-medium text-success">{savings}</div>}
        </div>
      );
    }
    case "Rating":
      return item.rating != null ? (
        <span className="flex items-center gap-1 text-foreground">
          <Star className="h-3.5 w-3.5 fill-warning text-warning" />
          {item.rating.toFixed(1)}
        </span>
      ) : (
        <span className="text-muted-foreground">—</span>
      );
    case "Reviews":
      return item.review_count != null ? (
        <span className="text-foreground">{item.review_count.toLocaleString()}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      );
    case "Availability":
      return item.price ? (
        <span className="flex items-center gap-1.5 text-success">
          <PackageCheck className="h-3.5 w-3.5" /> In stock / priced
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <PackageX className="h-3.5 w-3.5" /> Price not found
        </span>
      );
    case "Seller":
      return <span className="text-foreground">{item.platform}</span>;
    case "Official store":
      return item.platform.toLowerCase().includes("official") ? (
        <span className="flex items-center gap-1.5 text-primary">
          <ShieldCheck className="h-3.5 w-3.5" /> Yes
        </span>
      ) : (
        <span className="text-muted-foreground">No</span>
      );
    case "Price confidence":
      return item.confidence_score != null ? (
        <span className="text-foreground">{Math.round(item.confidence_score * 100)}%</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      );
    default:
      return <span className="text-muted-foreground">—</span>;
  }
}
