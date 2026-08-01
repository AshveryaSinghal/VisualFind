import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";
import { Activity, type LucideIcon } from "lucide-react";
import type { DailySearchCount } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface SearchTrendChartProps {
  data: DailySearchCount[];
  title?: string;
  icon?: LucideIcon;
  unitLabel?: string;
  totalSuffix?: string;
}

const LINE_COLOR = "hsl(var(--primary))";

function formatDayLabel(dateStr: string): string {
  const date = new Date(`${dateStr}T00:00:00`);
  return date.toLocaleDateString(undefined, { weekday: "short", day: "numeric" });
}

export function SearchTrendChart({
  data,
  title = "Search activity (last 7 days)",
  icon: Icon = Activity,
  unitLabel = "Searches",
  totalSuffix = "searches",
}: SearchTrendChartProps) {
  const chartData = data.map((point) => ({ ...point, label: formatDayLabel(point.date) }));
  const total = data.reduce((sum, point) => sum + point.count, 0);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-primary" />
          <CardTitle className="text-base">{title}</CardTitle>
        </div>
        <span className="text-xs text-muted-foreground">
          {total} {totalSuffix}
        </span>
      </CardHeader>
      <CardContent>
        <div className="h-48 w-full sm:h-56">
          <ResponsiveContainer>
            <AreaChart data={chartData} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="searchTrendFill" x1="0" y1="0" x2="0" y2="1">
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
              />
              <YAxis
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={28}
                allowDecimals={false}
              />
              <RechartsTooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                  color: "hsl(var(--popover-foreground))",
                }}
                formatter={(value: number) => [value, unitLabel]}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke={LINE_COLOR}
                strokeWidth={2.5}
                fill="url(#searchTrendFill)"
                activeDot={{ r: 5 }}
                dot={{ r: 3, strokeWidth: 0, fill: LINE_COLOR }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
