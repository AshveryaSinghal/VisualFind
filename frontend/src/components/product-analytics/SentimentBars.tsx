import { Smile, Meh, Frown, Sparkles, Calculator, Quote } from "lucide-react";
import type { ReviewSentiment } from "@/types";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/common/EmptyState";

interface SentimentBarsProps {
  sentiment: ReviewSentiment | null;
}

const ROWS = [
  { key: "positive_pct" as const, label: "Positive", icon: Smile, bar: "bg-success", text: "text-success" },
  { key: "neutral_pct" as const, label: "Neutral", icon: Meh, bar: "bg-warning", text: "text-warning" },
  { key: "negative_pct" as const, label: "Negative", icon: Frown, bar: "bg-destructive", text: "text-destructive" },
];

export function SentimentBars({ sentiment }: SentimentBarsProps) {
  if (!sentiment) {
    return (
      <EmptyState
        icon={Meh}
        title="No rating data for this listing"
        description="We need a star rating to estimate review sentiment."
        className="border-none py-10"
      />
    );
  }

  return (
    <div className="space-y-4">
      <div>
        {sentiment.is_estimate ? (
          <Badge variant="outline" className="gap-1 text-muted-foreground">
            <Calculator className="h-3 w-3" />
            Estimated from rating
          </Badge>
        ) : (
          <Badge variant="secondary" className="gap-1 border-primary/40 text-primary">
            <Sparkles className="h-3 w-3" />
            Real review analysis
          </Badge>
        )}
      </div>

      {ROWS.map(({ key, label, icon: Icon, bar, text }) => (
        <div key={key} className="space-y-1.5">
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Icon className={`h-4 w-4 ${text}`} />
              {label}
            </span>
            <span className={`font-semibold ${text}`}>{sentiment[key]}%</span>
          </div>
          <Progress value={sentiment[key]} indicatorClassName={bar} />
        </div>
      ))}

      {!sentiment.is_estimate && (sentiment.sample_positive || sentiment.sample_negative) && (
        <div className="space-y-2 border-t border-border pt-3">
          {sentiment.sample_positive && (
            <div className="flex gap-2 text-xs">
              <Quote className="mt-0.5 h-3 w-3 shrink-0 text-success" />
              <p className="text-muted-foreground">
                <span className="font-medium text-success">Positive review: </span>
                {sentiment.sample_positive}
              </p>
            </div>
          )}
          {sentiment.sample_negative && (
            <div className="flex gap-2 text-xs">
              <Quote className="mt-0.5 h-3 w-3 shrink-0 text-destructive" />
              <p className="text-muted-foreground">
                <span className="font-medium text-destructive">Negative review: </span>
                {sentiment.sample_negative}
              </p>
            </div>
          )}
        </div>
      )}

      <p className="pt-1 text-xs text-muted-foreground">{sentiment.basis}</p>
    </div>
  );
}
