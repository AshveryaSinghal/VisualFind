import { Sparkles, ThumbsUp, Hourglass, CircleHelp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/cn";

interface QuickSummaryCardProps {
  summary: string[];
  verdict: string;
}

function verdictStyle(verdict: string): { variant: "success" | "warning" | "muted"; icon: typeof ThumbsUp } {
  if (verdict === "Worth buying now") return { variant: "success", icon: ThumbsUp };
  if (verdict === "Better to wait") return { variant: "warning", icon: Hourglass };
  return { variant: "muted", icon: CircleHelp };
}

export function QuickSummaryCard({ summary, verdict }: QuickSummaryCardProps) {
  const { variant, icon: VerdictIcon } = verdictStyle(verdict);

  return (
    <div className="space-y-4">
      <ul className="space-y-2.5">
        {summary.map((line, index) => (
          <li key={index} className="flex items-start gap-2.5 text-sm text-foreground">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <span>{line}</span>
          </li>
        ))}
      </ul>

      {verdict && (
        <Badge variant={variant} className={cn("w-fit gap-1.5 px-3 py-1.5 text-sm")}>
          <VerdictIcon className="h-3.5 w-3.5" />
          {verdict}
        </Badge>
      )}
    </div>
  );
}
