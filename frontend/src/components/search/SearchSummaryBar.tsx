import { motion } from "framer-motion";
import { Clock, Sparkles, ShieldCheck, Tag, Zap } from "lucide-react";
import type { SearchResponse } from "@/types";
import { formatDurationMs, formatPrice } from "@/utils/format";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";

export function SearchSummaryBar({ response }: { response: SearchResponse }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl border border-border bg-card/50 px-5 py-4 text-sm"
    >
      {response.best_guess_label && (
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-muted-foreground">Identified as</span>
          <span className="font-medium text-foreground">{response.best_guess_label}</span>
        </div>
      )}

      {response.detected_brand && (
        <div className="flex items-center gap-2">
          <Tag className="h-4 w-4 text-primary" />
          <span className="text-muted-foreground">Brand</span>
          <Tooltip
            content={
              response.brand_confidence !== null
                ? `${Math.round((response.brand_confidence ?? 0) * 100)}% confidence`
                : "Confidence unknown"
            }
          >
            <span className="cursor-help font-medium text-foreground underline decoration-dotted underline-offset-4">
              {response.detected_brand}
            </span>
          </Tooltip>
        </div>
      )}

      {response.official_product_found && (
        <Badge variant="outline" className="border-primary/40 text-primary">
          <ShieldCheck className="h-3 w-3" />
          Official listing found
        </Badge>
      )}

      {response.fastest_delivery && (
        <Tooltip
          content={`${response.fastest_delivery.platform} · ${formatPrice(
            response.fastest_delivery.price,
            response.fastest_delivery.currency
          )}`}
        >
          <Badge variant="outline" className="border-success/40 text-success">
            <Zap className="h-3 w-3" />
            Fastest delivery: {response.fastest_delivery.platform}
            {response.fastest_delivery.delivery_estimate
              ? ` (${response.fastest_delivery.delivery_estimate})`
              : ""}
          </Badge>
        </Tooltip>
      )}

      <div className="ml-auto flex items-center gap-4 text-muted-foreground">
        {response.execution_time_ms !== null && (
          <span className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            {formatDurationMs(response.execution_time_ms)}
          </span>
        )}
        {response.from_cache && (
          <Badge variant="muted" className="text-[10px]">
            Cached result
          </Badge>
        )}
        <span>
          {response.trusted_matches_returned} of {response.total_matches_found} matches trusted ·{" "}
          {response.priced_count} priced
        </span>
      </div>
    </motion.div>
  );
}
