import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { ExternalLink, ShieldCheck, Trash2, Clock, Package, Tag } from "lucide-react";
import type { HistoryItem } from "@/types";
import { formatDateTimeInZone, formatDurationMs, formatPrice, formatRelativeDate } from "@/utils/format";
import { useAuth } from "@/context/AuthContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tooltip } from "@/components/ui/tooltip";

interface HistoryCardProps {
  item: HistoryItem;
  index?: number;
  onDelete: (id: number) => void;
  isDeleting: boolean;
}

const ACCENTS = [
  "from-indigo-500/20 to-indigo-500/5 text-indigo-500",
  "from-emerald-500/20 to-emerald-500/5 text-emerald-500",
  "from-amber-500/20 to-amber-500/5 text-amber-500",
  "from-rose-500/20 to-rose-500/5 text-rose-500",
  "from-sky-500/20 to-sky-500/5 text-sky-500",
  "from-fuchsia-500/20 to-fuchsia-500/5 text-fuchsia-500",
];

function accentFor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return ACCENTS[hash % ACCENTS.length];
}

export function HistoryCard({ item, index = 0, onDelete, isDeleting }: HistoryCardProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const label = item.best_guess_label ?? item.product_query ?? "Untitled search";
  const accent = accentFor(item.detected_brand ?? label);
  const initial = (item.detected_brand ?? label).trim().charAt(0).toUpperCase() || "?";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.03, 0.3) }}
    >
      <Card className="group flex h-full flex-col overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-xl">
        <button
          onClick={() => navigate(`/results/${item.id}`)}
          className="flex flex-1 flex-col text-left"
        >
          <div className="relative aspect-[4/3] w-full shrink-0 overflow-hidden bg-muted">
            {item.thumbnail ? (
              <img
                src={item.thumbnail}
                alt={label}
                loading="lazy"
                className="h-full w-full object-contain p-3 transition-transform duration-300 group-hover:scale-105"
              />
            ) : (
              <div
                className={`flex h-full w-full items-center justify-center bg-gradient-to-br text-4xl font-semibold ${accent}`}
              >
                {initial}
              </div>
            )}
            <div className="absolute right-2 top-2">
              <Tooltip content={formatDateTimeInZone(item.created_at, user?.timezone)}>
                <span className="rounded-full bg-background/90 px-2 py-1 text-xs text-muted-foreground shadow-sm">
                  {formatRelativeDate(item.created_at)}
                </span>
              </Tooltip>
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-4 p-5">
          <div className="space-y-1">
            <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-foreground">
              {label}
            </h3>
            {item.detected_brand && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Tag className="h-3 w-3" />
                {item.detected_brand}
                {item.official_domain && (
                  <Tooltip content={`Official domain: ${item.official_domain}`}>
                    <ShieldCheck className="h-3 w-3 text-primary" />
                  </Tooltip>
                )}
              </div>
            )}
          </div>

          <div className="mt-auto grid grid-cols-3 gap-2 border-t border-border pt-3 text-xs">
            <div className="space-y-0.5">
              <p className="flex items-center gap-1 text-muted-foreground">
                <Package className="h-3 w-3" /> Found
              </p>
              <p className="font-medium text-foreground">
                {item.filtered_count} / {item.result_count}
              </p>
            </div>
            <div className="space-y-0.5">
              <p className="text-muted-foreground">Lowest price</p>
              <p className="truncate font-medium text-foreground">
                {item.best_deal_price != null ? formatPrice(item.best_deal_price, null) : "—"}
              </p>
            </div>
            <div className="space-y-0.5">
              <p className="flex items-center gap-1 text-muted-foreground">
                <Clock className="h-3 w-3" /> Duration
              </p>
              <p className="font-medium text-foreground">
                {formatDurationMs(item.execution_time_ms)}
              </p>
            </div>
          </div>

          {item.best_deal_platform && (
            <Badge variant="secondary" className="w-fit">
              Best on {item.best_deal_platform}
            </Badge>
          )}
          </div>
        </button>

        <div className="flex items-center justify-end gap-1 border-t border-border px-3 py-2">
          <Tooltip content="View results">
            <Button variant="ghost" size="icon" onClick={() => navigate(`/results/${item.id}`)}>
              <ExternalLink className="h-4 w-4" />
            </Button>
          </Tooltip>
          <Tooltip content="Delete">
            <Button
              variant="ghost"
              size="icon"
              isLoading={isDeleting}
              onClick={() => onDelete(item.id)}
              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </Tooltip>
        </div>
      </Card>
    </motion.div>
  );
}
