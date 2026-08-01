import { motion } from "framer-motion";
import { Layers } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { formatCompactNumber } from "@/utils/format";

interface EmbeddingProgressCardProps {
  embedded: number;
  total: number;
  progressPct: number;
  index?: number;
}

export function EmbeddingProgressCard({ embedded, total, progressPct, index = 0 }: EmbeddingProgressCardProps) {
  const remaining = Math.max(total - embedded, 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
    >
      <Card>
        <CardContent className="space-y-3 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Embedding generation progress</p>
              <p className="text-2xl font-bold tracking-tight text-foreground">{progressPct.toFixed(1)}%</p>
            </div>
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Layers className="h-5 w-5" />
            </div>
          </div>
          <Progress value={progressPct} />
          <p className="text-xs text-muted-foreground">
            {formatCompactNumber(embedded)} embedded
            {remaining > 0 ? ` · ${formatCompactNumber(remaining)} pending` : " · fully caught up"}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  );
}
