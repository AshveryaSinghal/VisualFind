import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";
import { TrendingDown, TrendingUp, Minus, History } from "lucide-react";
import type { PriceTrendPoint } from "@/types";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import { formatPrice, formatDateTime } from "@/utils/format";
import { cn } from "@/utils/cn";

interface PriceHistoryChartProps {
  points: PriceTrendPoint[];
  currency: string | null;
  direction: "up" | "down" | "same" | null;
  changePercent: number | null;
}

const LINE_COLOR = "hsl(var(--primary))";

export function PriceHistoryChart({ points, currency, direction, changePercent }: PriceHistoryChartProps) {
  if (points.length < 2) {
    return (
      <EmptyState
        icon={History}
        title="Not enough price history yet"
        description={
          points.length === 1
            ? "We've recorded one price so far. Check back after this product is searched again to see a trend."
            : "This is the first time we've tracked this product's price. A trend will appear the next time it's viewed."
        }
        className="border-none py-10"
      />
    );
  }

  const chartData = points.map((point) => ({
    price: point.price,
    label: formatDateTime(point.recorded_at),
    marketplace: point.marketplace,
  }));

  const trendBadge =
    direction === "down" ? (
      <Badge variant="success">
        <TrendingDown className="h-3 w-3" />
        {changePercent !== null ? `${Math.abs(changePercent).toFixed(0)}% down` : "Falling"}
      </Badge>
    ) : direction === "up" ? (
      <Badge variant="destructive">
        <TrendingUp className="h-3 w-3" />
        {changePercent !== null ? `${changePercent.toFixed(0)}% up` : "Rising"}
      </Badge>
    ) : (
      <Badge variant="muted">
        <Minus className="h-3 w-3" />
        Steady
      </Badge>
    );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {points.length} recorded price {points.length === 1 ? "point" : "points"}
        </p>
        {trendBadge}
      </div>

      <div className="h-56 w-full sm:h-64">
        <ResponsiveContainer>
          <AreaChart data={chartData} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="priceHistoryFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={LINE_COLOR} stopOpacity={0.35} />
                <stop offset="100%" stopColor={LINE_COLOR} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="4 8" stroke="hsl(var(--border))" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={64}
              tickFormatter={(value: number) => formatPrice(value, currency)}
              domain={["dataMin - dataMin * 0.05", "dataMax + dataMax * 0.05"]}
            />
            <RechartsTooltip
              contentStyle={{
                background: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 12,
                color: "hsl(var(--popover-foreground))",
              }}
              formatter={(value: number) => [formatPrice(value, currency), "Price"]}
              labelFormatter={(label: string, payload) => {
                const marketplace = payload?.[0]?.payload?.marketplace;
                return marketplace ? `${label} · ${marketplace}` : label;
              }}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke={LINE_COLOR}
              strokeWidth={2.5}
              fill="url(#priceHistoryFill)"
              activeDot={{ r: 5 }}
              dot={{ r: 3, strokeWidth: 0, fill: LINE_COLOR }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <p className={cn("text-xs text-muted-foreground")}>
        Based on prices VisualFind has actually recorded for this product over time.
      </p>
    </div>
  );
}
