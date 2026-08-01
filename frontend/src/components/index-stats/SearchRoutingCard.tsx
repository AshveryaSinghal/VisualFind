import { Route } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/common/EmptyState";
import { formatCompactNumber } from "@/utils/format";

interface SearchRoutingCardProps {
  totalSearches: number;
  internalIndexSearches: number;
  internalIndexSharePct: number | null;
  lensFallbackSearches: number;
  lensFallbackSharePct: number | null;
  cacheHitSearches: number;
  cacheHitRatePct: number | null;
}

interface RowProps {
  label: string;
  count: number;
  pct: number | null;
  indicatorClassName: string;
}

function RoutingRow({ label, count, pct, indicatorClassName }: RowProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-foreground">{label}</span>
        <span className="text-muted-foreground">
          {formatCompactNumber(count)} {pct != null ? `(${pct}%)` : ""}
        </span>
      </div>
      <Progress value={pct ?? 0} indicatorClassName={indicatorClassName} />
    </div>
  );
}

export function SearchRoutingCard({
  totalSearches,
  internalIndexSearches,
  internalIndexSharePct,
  lensFallbackSearches,
  lensFallbackSharePct,
  cacheHitSearches,
  cacheHitRatePct,
}: SearchRoutingCardProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <Route className="h-4 w-4 text-primary" />
        <CardTitle className="text-base">Google Lens results vs. internal-index supplement</CardTitle>
      </CardHeader>
      <CardContent>
        {totalSearches === 0 ? (
          <EmptyState icon={Route} title="No searches yet" description="Search routing will appear here once searches start coming in." className="border-none py-8" />
        ) : (
          <div className="space-y-4">
            <RoutingRow
              label="Google Lens + internal-index recommendations"
              count={internalIndexSearches}
              pct={internalIndexSharePct}
              indicatorClassName="bg-success"
            />
            <RoutingRow
              label="Google Lens results only"
              count={lensFallbackSearches}
              pct={lensFallbackSharePct}
              indicatorClassName="bg-warning"
            />
            <RoutingRow
              label="Served from cache"
              count={cacheHitSearches}
              pct={cacheHitRatePct}
              indicatorClassName="bg-primary"
            />
            <p className="pt-1 text-xs text-muted-foreground">
              Google Lens is always the primary source; the internal index only ever adds a few supplemental recommendations on top. Shares are of live (non-cached) searches; cache rate is of all searches.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
