import { BarChart3, CheckCircle2, Clock, Package, Percent, Search, ShieldCheck, Store, Tag, Zap } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/analytics/StatCard";
import { TopListCard } from "@/components/analytics/TopListCard";
import { SearchTrendChart } from "@/components/analytics/SearchTrendChart";
import { BestDealCard } from "@/components/analytics/BestDealCard";
import { ErrorState } from "@/components/common/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { useAnalytics } from "@/hooks/useAnalytics";
import { formatCompactNumber, formatDurationMs } from "@/utils/format";

export function AnalyticsPage() {
  const { data, isLoading, isError, error, refetch } = useAnalytics();

  return (
    <div className="container py-10">
      <PageHeader
        eyebrow="Insights"
        title="Analytics"
        description="Aggregated stats computed from every search VisualFind has run."
      />

      <div className="mt-8">
        {isLoading && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-28 w-full rounded-xl" />
            ))}
          </div>
        )}

        {isError && <ErrorState error={error} onRetry={() => refetch()} />}

        {data && data.total_searches === 0 && (
          <EmptyState
            icon={BarChart3}
            title="No analytics yet"
            description="Run a few searches and this dashboard will fill in automatically."
          />
        )}

        {data && data.total_searches > 0 && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                icon={Search}
                label="Total searches"
                value={formatCompactNumber(data.total_searches)}
                hint={`${data.searches_last_7_days} in the last 7 days`}
                index={0}
              />
              <StatCard
                icon={Clock}
                label="Avg. search time"
                value={formatDurationMs(data.average_search_time_ms)}
                hint={data.fastest_search_ms != null ? `Fastest: ${formatDurationMs(data.fastest_search_ms)}` : undefined}
                accent="warning"
                index={1}
              />
              <StatCard
                icon={Package}
                label="Avg. products found"
                value={data.average_products_found?.toFixed(1) ?? "—"}
                hint={`${formatCompactNumber(data.total_products_found)} total found`}
                accent="success"
                index={2}
              />
              <StatCard
                icon={Percent}
                label="Avg. priced products"
                value={data.average_priced_products?.toFixed(1) ?? "—"}
                index={3}
              />
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
              <StatCard
                icon={CheckCircle2}
                label="Searches with a live price"
                value={data.price_hit_rate != null ? `${data.price_hit_rate}%` : "—"}
                accent="success"
                index={4}
              />
              <StatCard
                icon={ShieldCheck}
                label="Matched an official listing"
                value={data.official_match_rate != null ? `${data.official_match_rate}%` : "—"}
                index={5}
              />
              <StatCard
                icon={Zap}
                label="Fastest search"
                value={data.fastest_search_ms != null ? formatDurationMs(data.fastest_search_ms) : "—"}
                accent="warning"
                index={6}
              />
            </div>

            {data.best_deal_found && <BestDealCard deal={data.best_deal_found} />}

            <SearchTrendChart data={data.searches_by_day} />

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <TopListCard
                title="Top searched products"
                icon={Search}
                data={data.most_searched_products}
                emptyMessage="No repeat product searches yet."
              />
              <TopListCard
                title="Top platforms (best deal)"
                icon={Store}
                data={data.most_searched_platforms}
                emptyMessage="No best-deal platform data yet."
              />
              <TopListCard
                title="Top brands (approximate)"
                icon={Tag}
                data={data.most_searched_brands}
                emptyMessage="No brand data yet."
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
