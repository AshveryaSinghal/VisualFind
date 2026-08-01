import type { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/utils/cn";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  hint?: string;
  accent?: "primary" | "success" | "warning";
  index?: number;
}

const ACCENT_STYLES: Record<NonNullable<StatCardProps["accent"]>, string> = {
  primary: "bg-primary/10 text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
};

export function StatCard({ icon: Icon, label, value, hint, accent = "primary", index = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
    >
      <Card>
        <CardContent className="flex items-start justify-between gap-4 p-5">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold tracking-tight text-foreground">{value}</p>
            {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
          </div>
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", ACCENT_STYLES[accent])}>
            <Icon className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
