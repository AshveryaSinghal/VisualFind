import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Heart, History, ListFilter, Sparkles, TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProductCard } from "@/components/search/ProductCard";
import { useRecommendations } from "@/hooks/usePersonalization";
import type { RecommendationItem, RecommendationReason } from "@/types";

const REASON_ICON: Record<RecommendationReason, typeof Sparkles> = {
  search_history: History,
  viewed: Heart,
  category: TrendingUp,
  compared: ListFilter,
  budget: ListFilter,
};

function RecommendationCard({ item, index }: { item: RecommendationItem; index: number }) {
  const Icon = REASON_ICON[item.reason_type] ?? Sparkles;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon className="h-3.5 w-3.5 text-primary" />
        <span className="truncate">{item.reason_text}</span>
      </div>
      <ProductCard product={item.product} index={index} />
    </div>
  );
}

function RecommendationsSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="space-y-2">
          <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
          <div className="aspect-square w-full animate-pulse rounded-xl bg-muted" />
          <div className="h-4 w-full animate-pulse rounded bg-muted" />
          <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

export function RecommendationsPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useRecommendations();

  return (
    <div className="container py-10">
      <PageHeader
        eyebrow="Personalized"
        title="For You"
        description="Recommendations built from your searches, viewed products, comparisons, and saved preferences."
        action={
          <Button variant="outline" onClick={() => navigate("/profile?tab=preferences")}>
            <ListFilter className="h-4 w-4" />
            Edit preferences
          </Button>
        }
      />

      <div className="mt-8">
        {isLoading && <RecommendationsSkeleton />}

        {isError && <ErrorState error={error} onRetry={() => refetch()} />}

        {!isLoading && !isError && data && data.items.length === 0 && (
          <EmptyState
            icon={Sparkles}
            title={
              data.has_enough_signal
                ? "Nothing to recommend just yet"
                : "We don't know your taste yet"
            }
            description={
              data.has_enough_signal
                ? "Search for a few more products, view some results, or widen your budget in Preferences to see picks here."
                : "Run a search or two, view some products, and set your favorite categories and budget in Preferences - recommendations will show up here."
            }
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button size="sm" onClick={() => navigate("/search")}>
                  Start a search
                </Button>
                <Button size="sm" variant="outline" onClick={() => navigate("/profile?tab=preferences")}>
                  Set preferences
                </Button>
              </div>
            }
          />
        )}

        {!isLoading && !isError && data && data.items.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="space-y-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="muted">{data.items.length} picks</Badge>
              <span className="text-xs text-muted-foreground">
                Updated {new Date(data.generated_at).toLocaleTimeString()}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {data.items.map((item, index) => (
                <RecommendationCard key={`${item.product.link}-${index}`} item={item} index={index} />
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
