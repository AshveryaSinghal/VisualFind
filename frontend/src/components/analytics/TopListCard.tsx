import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from "recharts";
import type { LucideIcon } from "lucide-react";
import type { NamedCount } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/EmptyState";
import { titleCase } from "@/utils/format";

interface TopListCardProps {
  title: string;
  icon: LucideIcon;
  data: NamedCount[];
  emptyMessage: string;
}

const BAR_COLOR = "hsl(var(--primary))";
const MAX_LABEL_LENGTH = 20;

function truncateLabel(name: string): string {
  if (name.length <= MAX_LABEL_LENGTH) return name;
  return `${name.slice(0, MAX_LABEL_LENGTH - 1).trimEnd()}…`;
}

export function TopListCard({ title, icon: Icon, data, emptyMessage }: TopListCardProps) {
  const chartData = data
    .slice(0, 8)
    .map((item) => {
      const fullName = titleCase(item.name);
      return { ...item, name: truncateLabel(fullName), fullName };
    })
    .reverse();

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <Icon className="h-4 w-4 text-primary" />
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {chartData.length === 0 ? (
          <EmptyState icon={Icon} title="No data yet" description={emptyMessage} className="border-none py-8" />
        ) : (
          <div style={{ width: "100%", height: Math.max(chartData.length * 40, 120) }}>
            <ResponsiveContainer>
              <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={130}
                  interval={0}
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                />
                <RechartsTooltip
                  cursor={{ fill: "hsl(var(--accent))" }}
                  labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName ?? label}
                  contentStyle={{
                    background: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                    color: "hsl(var(--popover-foreground))",
                  }}
                />
                <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
                  {chartData.map((_, index) => (
                    <Cell key={index} fill={BAR_COLOR} fillOpacity={0.55 + (0.45 * index) / chartData.length} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
