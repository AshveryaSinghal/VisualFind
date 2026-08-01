import { useNavigate } from "react-router-dom";
import { ExternalLink, Star, Store, Trash2 } from "lucide-react";
import type { SavedProduct } from "@/types";
import { formatPrice } from "@/utils/format";
import { Badge } from "@/components/ui/badge";
import { buttonVariants, Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/utils/cn";

interface SavedProductCardProps {
  item: SavedProduct;
  onRemove: (id: number) => void;
  isRemoving: boolean;
}

export function SavedProductCard({ item, onRemove, isRemoving }: SavedProductCardProps) {
  const navigate = useNavigate();

  const openAnalytics = () => {
    const params = new URLSearchParams();
    params.set("title", item.product_name);
    if (item.platform) params.set("platform", item.platform);
    if (item.currency) params.set("currency", item.currency);
    if (item.thumbnail) params.set("thumbnail", item.thumbnail);
    if (item.link) params.set("link", item.link);
    if (item.price !== null && item.price !== undefined) params.set("price", String(item.price));
    if (item.rating !== null && item.rating !== undefined) params.set("rating", String(item.rating));
    if (item.review_count !== null && item.review_count !== undefined) {
      params.set("review_count", String(item.review_count));
    }
    navigate(`/product-analytics?${params.toString()}`);
  };

  return (
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
      aria-label={`View analytics for ${item.product_name}`}
      className="group flex h-full flex-col overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:shadow-xl cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <div className="relative aspect-square w-full overflow-hidden bg-muted">
        {item.thumbnail ? (
          <img
            src={item.thumbnail}
            alt={item.product_name}
            loading="lazy"
            className="h-full w-full object-contain p-4 transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            <Store className="h-10 w-10" />
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        {item.platform && (
          <Badge variant="secondary" className="w-fit truncate">
            {item.platform}
          </Badge>
        )}

        <h3 className="line-clamp-2 min-h-[2.75rem] text-sm font-medium leading-snug text-foreground">
          {item.product_name}
        </h3>

        <div className="flex items-baseline gap-2">
          <span className="text-lg font-bold tracking-tight text-foreground">
            {formatPrice(item.price, item.currency)}
          </span>
        </div>

        {item.rating !== null && item.rating !== undefined && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Star className="h-3.5 w-3.5 fill-warning text-warning" />
            {item.rating.toFixed(1)}
            {item.review_count ? ` (${item.review_count.toLocaleString()})` : ""}
          </span>
        )}

        <div className="mt-auto flex items-center gap-2 pt-2">
          {item.link && (
            <a
              href={item.link}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(event) => event.stopPropagation()}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "flex-1")}
            >
              View
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
          <Button
            variant="outline"
            size="sm"
            isLoading={isRemoving}
            onClick={(event) => {
              event.stopPropagation();
              onRemove(item.id);
            }}
            className={cn("gap-1.5 text-destructive hover:bg-destructive/10 hover:text-destructive", !item.link && "flex-1")}
          >
            <Trash2 className="h-3.5 w-3.5" />
            Remove
          </Button>
        </div>
      </div>
    </Card>
  );
}
