import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Star,
  ExternalLink,
  BadgeCheck,
  Store,
  ShieldCheck,
  PackageCheck,
  PackageX,
  HelpCircle,
  Check,
  Scale,
  BarChart3,
  Zap,
} from "lucide-react";
import type { PurchaseLink } from "@/types";
import { formatPrice, formatSavings } from "@/utils/format";
import { buildProductAnalyticsSearch } from "@/utils/productAnalyticsLink";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { useCompare } from "@/context/CompareContext";
import { SaveButton } from "@/components/common/SaveButton";

interface ProductCardProps {
  product: PurchaseLink;
  index?: number;

  hideCompareToggle?: boolean;
  /** Tab-local object URL for the photo the person searched with. Used
   * only as a visual placeholder when this result has no product image
   * of its own - never uploaded or persisted anywhere. */
  fallbackImage?: string | null;
  /** When the card renders somewhere narrower than the main results grid
   * (e.g. inside the AI assistant's chat column), force the Compare and
   * Analytics buttons to icon-only so they never overlap or clip. The
   * primary "View product" button is unaffected. */
  compactActions?: boolean;
}

const CONFIDENCE_LABEL: Record<"high" | "medium" | "low", string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

function confidenceTier(score: number | null): "high" | "medium" | "low" | null {
  if (score === null || score === undefined) return null;
  if (score >= 0.8) return "high";
  if (score >= 0.55) return "medium";
  return "low";
}

export function ProductCard({
  product,
  index = 0,
  hideCompareToggle = false,
  fallbackImage = null,
  compactActions = false,
}: ProductCardProps) {
  const savingsLabel = formatSavings(product.savings, product.currency);
  const tier = confidenceTier(product.confidence_score);
  const isOfficial = product.platform.toLowerCase().includes("official");
  const hasPrice = product.price !== null && product.price !== undefined;
  const { isSelected, toggle, isFull } = useCompare();
  const selected = isSelected(product);
  const disabledToCompare = !selected && isFull;
  const navigate = useNavigate();

  const openAnalytics = () => {
    navigate(`/product-analytics?${buildProductAnalyticsSearch(product)}`);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index * 0.05, 0.4), ease: "easeOut" }}
    >
      <Card
        role="link"
        tabIndex={0}
        onClick={openAnalytics}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openAnalytics();
          }
        }}
        aria-label={`View analytics for ${product.title}`}
        className={cn(
          "group relative flex h-full flex-col overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-xl cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
          product.is_best_deal && "ring-2 ring-success/60",
          selected && "ring-2 ring-primary"
        )}
      >
        {product.is_best_deal && (
          <div className="absolute left-3 top-3 z-10">
            <Tooltip content={product.best_deal_reason ?? "Best overall value among these results"}>
              <Badge variant="success" className="shadow">
                <BadgeCheck className="h-3 w-3" />
                Best deal
              </Badge>
            </Tooltip>
          </div>
        )}

        {isOfficial && (
          <div className="absolute right-3 top-3 z-10">
            <Tooltip content="Verified official brand website">
              <Badge variant="outline" className="border-primary/40 bg-background/90 text-primary shadow">
                <ShieldCheck className="h-3 w-3" />
                Official Store
              </Badge>
            </Tooltip>
          </div>
        )}

        <div className="relative aspect-square w-full overflow-hidden bg-muted">
          <div className="absolute bottom-2 right-2 z-10">
            <SaveButton product={product} />
          </div>
          {product.thumbnail ? (
            <img
              src={product.thumbnail}
              alt={product.title}
              loading="lazy"
              className="h-full w-full object-contain p-4 transition-transform duration-300 group-hover:scale-105"
            />
          ) : fallbackImage ? (
            <>
              <img
                src={fallbackImage}
                alt="Your uploaded reference photo"
                loading="lazy"
                className="h-full w-full object-contain p-4 opacity-80 transition-transform duration-300 group-hover:scale-105"
              />
              <span className="absolute bottom-2 left-2 z-10 rounded-full bg-background/85 px-2 py-0.5 text-[10px] font-medium text-muted-foreground shadow-sm backdrop-blur-sm">
                Your photo
              </span>
            </>
          ) : (
            <div className="flex h-full w-full items-center justify-center text-muted-foreground">
              <Store className="h-10 w-10" />
            </div>
          )}

        </div>

        <div className="flex flex-1 flex-col gap-3 p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-1.5">
              <Badge variant="secondary" className="truncate">
                {product.platform}
              </Badge>
              {product.is_quick_commerce && (
                <Tooltip
                  content={
                    product.delivery_estimate
                      ? `Typical delivery window: ${product.delivery_estimate}`
                      : "Quick-commerce delivery"
                  }
                >
                  <Badge variant="outline" className="gap-1 border-success/40 text-success">
                    <Zap className="h-3 w-3" />
                    {product.delivery_estimate ?? "Fast delivery"}
                  </Badge>
                </Tooltip>
              )}
            </div>
            {tier && (
              <Tooltip content={`${CONFIDENCE_LABEL[tier]} price extraction`}>
                <span
                  className={cn(
                    "flex items-center gap-1 text-xs font-medium",
                    tier === "high" && "text-success",
                    tier === "medium" && "text-warning",
                    tier === "low" && "text-muted-foreground"
                  )}
                >
                  <HelpCircle className="h-3 w-3" />
                  {Math.round((product.confidence_score ?? 0) * 100)}%
                </span>
              </Tooltip>
            )}
          </div>

          {product.brand && (
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {product.brand}
            </span>
          )}

          <h3 className="line-clamp-2 min-h-[2.75rem] text-sm font-medium leading-snug text-foreground">
            {product.title}
          </h3>

          <div className="flex items-baseline gap-2">
            {hasPrice ? (
              <span className="text-xl font-bold tracking-tight text-foreground">
                {formatPrice(product.price, product.currency)}
              </span>
            ) : (
              <span className="text-sm font-medium text-muted-foreground">Price unavailable</span>
            )}
            {savingsLabel && (
              <span className="text-xs font-medium text-success">{savingsLabel}</span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {product.rating !== null && product.rating !== undefined && (
              <span className="flex items-center gap-1">
                <Star className="h-3.5 w-3.5 fill-warning text-warning" />
                {product.rating.toFixed(1)}
                {product.review_count !== null && product.review_count !== undefined && (
                  <span>({product.review_count.toLocaleString()})</span>
                )}
              </span>
            )}
            <span className="flex items-center gap-1 capitalize">
              {hasPrice ? (
                <>
                  <PackageCheck className="h-3.5 w-3.5 text-success" />
                  {(product.price_source ?? "live price").replace(/_/g, " ")}
                </>
              ) : (
                <>
                  <PackageX className="h-3.5 w-3.5" />
                  Price not found
                </>
              )}
            </span>
          </div>

          <div className="mt-auto flex flex-col gap-2 pt-2">
            <a
              href={product.link}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(event) => event.stopPropagation()}
              className={cn(buttonVariants({ size: "sm" }), "w-full min-w-0 gap-1.5")}
            >
              <span className="truncate">View product</span>
              <ExternalLink className="h-3.5 w-3.5 shrink-0" />
            </a>
            <div className="flex items-center gap-2">
              {!hideCompareToggle && (
                <Tooltip
                  wrapperClassName="min-w-0 flex-1"
                  content={
                    disabledToCompare
                      ? "You can compare up to 4 products at once"
                      : selected
                      ? "Remove from comparison"
                      : "Add to comparison"
                  }
                >
                  <button
                    type="button"
                    aria-pressed={selected}
                    aria-label={selected ? "Remove from comparison" : "Add to comparison"}
                    disabled={disabledToCompare}
                    onClick={(event) => {
                      event.stopPropagation();
                      toggle(product);
                    }}
                    className={cn(
                      buttonVariants({ variant: selected ? "default" : "outline", size: "sm" }),
                      "w-full min-w-0 justify-center gap-1.5",
                      !selected && "border-primary/40 text-primary hover:bg-primary/10 hover:text-primary",
                      disabledToCompare && "cursor-not-allowed opacity-50"
                    )}
                  >
                    {selected ? (
                      <Check className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <Scale className="h-3.5 w-3.5 shrink-0" />
                    )}
                    {!compactActions && <span className="truncate">Compare</span>}
                  </button>
                </Tooltip>
              )}
              <Tooltip
                wrapperClassName="min-w-0 flex-1"
                content="View price history, review sentiment & a quick summary"
              >
                <button
                  type="button"
                  aria-label={`View analytics for ${product.title}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    openAnalytics();
                  }}
                  className={cn(
                    buttonVariants({ variant: "outline", size: "sm" }),
                    "w-full min-w-0 justify-center gap-1.5"
                  )}
                >
                  <BarChart3 className="h-3.5 w-3.5 shrink-0" />
                  {!compactActions && <span className="truncate">Analytics</span>}
                </button>
              </Tooltip>
            </div>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
