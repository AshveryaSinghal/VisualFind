import { motion } from "framer-motion";
import {
  Sparkles,
  BadgeCheck,
  ExternalLink,
  TrendingDown,
  TrendingUp,
  Star,
  ShieldCheck,
  History,
  SearchX,
} from "lucide-react";
import type { AIRecommendation } from "@/types";
import { formatPrice } from "@/utils/format";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/utils/cn";

interface RecommendationCardProps {
  recommendation: AIRecommendation;
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const {
    product,
    reason,
    why_it_matches,
    money_saved,
    is_official_store,
    alternatives,
    is_exact_match,
    price_history,
  } = recommendation;

  if (!product) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="space-y-3"
    >
      {!is_exact_match && (
        <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-2.5 text-sm text-warning">
          <SearchX className="mt-0.5 h-4 w-4 shrink-0" />
          We couldn&apos;t find the exact product on a trusted platform, so here&apos;s the
          closest available alternative.
        </div>
      )}

      <Card className="overflow-hidden border-primary/30 bg-gradient-to-br from-primary/5 via-card to-card">
        <div className="flex items-center gap-2 border-b border-primary/20 bg-primary/10 px-5 py-2.5">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">
            AI Recommended Pick
          </span>
        </div>

        <div className="grid grid-cols-1 gap-6 p-5 sm:grid-cols-[8rem_1fr] sm:p-6">
          <div className="flex h-32 w-full items-center justify-center overflow-hidden rounded-lg bg-muted sm:w-32">
            {product.thumbnail ? (
              <img
                src={product.thumbnail}
                alt={product.title}
                className="h-full w-full object-contain"
              />
            ) : (
              <Sparkles className="h-8 w-8 text-muted-foreground" />
            )}
          </div>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{product.platform}</Badge>
                {is_official_store && (
                  <Badge variant="success">
                    <BadgeCheck className="h-3 w-3" />
                    Official Store
                  </Badge>
                )}
                {product.is_best_deal && (
                  <Badge variant="warning">
                    <TrendingDown className="h-3 w-3" />
                    Best Deal
                  </Badge>
                )}
                {product.rating != null && (
                  <Badge variant="outline">
                    <Star className="h-3 w-3 fill-current text-warning" />
                    {product.rating.toFixed(1)}
                    {product.review_count ? ` (${product.review_count})` : ""}
                  </Badge>
                )}
              </div>
              <h3 className="text-lg font-semibold leading-snug text-foreground">
                {product.title}
              </h3>
              {product.brand && (
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Brand: {product.brand}
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <span className="text-2xl font-bold text-foreground">
                {formatPrice(product.price, product.currency)}
              </span>
              {money_saved != null && money_saved > 0 && (
                <span className="mb-0.5 text-sm font-medium text-success">
                  You save {formatPrice(money_saved, product.currency)}
                </span>
              )}
            </div>

            {(reason || why_it_matches) && (
              <div className="space-y-1.5 rounded-lg border border-border bg-background/60 p-3.5 text-sm">
                {reason && (
                  <p className="flex items-start gap-2 text-foreground">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    {reason}
                  </p>
                )}
                {why_it_matches && (
                  <p className="pl-6 text-muted-foreground">{why_it_matches}</p>
                )}
              </div>
            )}

            {product.is_best_deal && product.best_deal_reason && (
              <div className="flex items-start gap-2 rounded-lg border border-success/30 bg-success/5 p-3.5 text-sm text-foreground">
                <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                <span>
                  <span className="font-medium">Why this is the best deal: </span>
                  {product.best_deal_reason}
                </span>
              </div>
            )}

            {price_history && (
              <div className="flex items-start gap-2 rounded-lg border border-border bg-background/60 p-3.5 text-sm">
                <History className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                {price_history.first_time ? (
                  <span className="text-muted-foreground">{price_history.message}</span>
                ) : (
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-foreground">
                    <span className="text-muted-foreground line-through">
                      {formatPrice(price_history.previous_price, product.currency)}
                    </span>
                    <span>→</span>
                    <span className="font-medium">
                      {formatPrice(price_history.current_price, product.currency)}
                    </span>
                    {price_history.direction === "up" && (
                      <Badge variant="warning">
                        <TrendingUp className="h-3 w-3" />
                        {price_history.change_percent}% since last tracked
                      </Badge>
                    )}
                    {price_history.direction === "down" && (
                      <Badge variant="success">
                        <TrendingDown className="h-3 w-3" />
                        {Math.abs(price_history.change_percent ?? 0)}% since last tracked
                      </Badge>
                    )}
                    {price_history.direction === "same" && (
                      <Badge variant="outline">Unchanged since last tracked</Badge>
                    )}
                  </span>
                )}
              </div>
            )}

            <a
              href={product.link}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(buttonVariants({ size: "lg" }), "w-full sm:w-auto")}
            >
              Buy Now
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>

        {alternatives.length > 0 && (
          <div className="border-t border-border px-5 py-4 sm:px-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Alternative options
            </p>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
              {alternatives.map((alt, index) => (
                <a
                  key={`${alt.link}-${index}`}
                  href={alt.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-accent"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-foreground">
                      {alt.platform}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatPrice(alt.price, alt.currency)}
                    </span>
                  </span>
                  <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </a>
              ))}
            </div>
          </div>
        )}
      </Card>
    </motion.div>
  );
}
