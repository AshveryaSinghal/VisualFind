import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { motion } from "framer-motion";
import {
  Star,
  ExternalLink,
  Trophy,
  Sparkles,
  IndianRupee,
  ShieldCheck,
  MessageSquareText,
  Gauge,
  RotateCcw,
} from "lucide-react";
import type { ComparePreferences, PurchaseLink, SmartCompareResponse } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants, Button } from "@/components/ui/button";
import { formatPrice } from "@/utils/format";
import { cn } from "@/utils/cn";

interface CompareResultProps {
  productA: PurchaseLink;
  productB: PurchaseLink;
  preferences: ComparePreferences;
  result: SmartCompareResponse;
  onStartOver: () => void;
}

const CHART_COLOR_A = "hsl(var(--primary))";
const CHART_COLOR_B = "hsl(var(--warning))";

export function CompareResult({
  productA,
  productB,
  preferences,
  result,
  onStartOver,
}: CompareResultProps) {
  const chartData = [
    {
      metric: "Price",
      [productA.platform]: result.value_scores_a.price_score,
      [productB.platform]: result.value_scores_b.price_score,
    },
    {
      metric: "Rating",
      [productA.platform]: result.value_scores_a.rating_score,
      [productB.platform]: result.value_scores_b.rating_score,
    },
    {
      metric: "Reviews",
      [productA.platform]: result.value_scores_a.reviews_score,
      [productB.platform]: result.value_scores_b.reviews_score,
    },
    {
      metric: "Overall value",
      [productA.platform]: result.value_scores_a.overall_value_score,
      [productB.platform]: result.value_scores_b.overall_value_score,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-2xl border border-primary/30 bg-gradient-to-br from-primary/10 via-card to-card p-5"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <Trophy className="h-5 w-5" />
            </div>
            <div>
              <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                AI recommendation {!result.used_ai && "(rule-based fallback)"}
              </p>
              <h3 className="mt-0.5 text-lg font-semibold text-foreground">{result.headline}</h3>
            </div>
          </div>
          {result.confidence != null && (
            <div className="flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
              <Gauge className="h-3.5 w-3.5" />
              {Math.round(result.confidence * 100)}% confident
            </div>
          )}
        </div>

        <p className="mt-4 text-sm leading-relaxed text-foreground/90">
          {result.personalized_reason}
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <VerdictChip icon={IndianRupee} label="Price" text={result.price_verdict} />
          <VerdictChip icon={Star} label="Quality" text={result.quality_verdict} />
          <VerdictChip icon={ShieldCheck} label="Overall value" text={result.value_verdict} />
        </div>
      </motion.div>

      {}
      <div className="grid gap-4 sm:grid-cols-2">
        <ProductCard
          product={productA}
          isWinner={result.winner_index === 0}
          features={result.feature_highlights_a}
          score={result.value_scores_a.overall_value_score}
        />
        <ProductCard
          product={productB}
          isWinner={result.winner_index === 1}
          features={result.feature_highlights_b}
          score={result.value_scores_b.overall_value_score}
        />
      </div>

      {}
      <Card>
        <CardHeader className="flex-row items-center gap-2 space-y-0">
          <Gauge className="h-4 w-4 text-primary" />
          <p className="text-base font-semibold text-foreground">Score breakdown</p>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-xs text-muted-foreground">
            Scores are computed from real price, rating, and review data — weighted toward{" "}
            {preferences.priority === "price" ? "price" : "quality"} since that's what you said
            matters more.
          </p>
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} margin={{ left: -16, right: 16, top: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="metric"
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                />
                <RechartsTooltip
                  cursor={{ fill: "hsl(var(--accent))" }}
                  contentStyle={{
                    background: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                    color: "hsl(var(--popover-foreground))",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar
                  dataKey={productA.platform}
                  fill={CHART_COLOR_A}
                  radius={[6, 6, 0, 0]}
                  maxBarSize={48}
                />
                <Bar
                  dataKey={productB.platform}
                  fill={CHART_COLOR_B}
                  radius={[6, 6, 0, 0]}
                  maxBarSize={48}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-center">
        <Button variant="ghost" size="sm" onClick={onStartOver}>
          <RotateCcw className="h-3.5 w-3.5" />
          Start a new comparison
        </Button>
      </div>
    </div>
  );
}

function VerdictChip({
  icon: Icon,
  label,
  text,
}: {
  icon: typeof Star;
  label: string;
  text: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card/60 p-3">
      <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-foreground">{text}</p>
    </div>
  );
}

function ProductCard({
  product,
  isWinner,
  features,
  score,
}: {
  product: PurchaseLink;
  isWinner: boolean;
  features: string[];
  score: number;
}) {
  return (
    <Card
      className={cn(
        "relative overflow-hidden transition",
        isWinner && "border-success shadow-[0_0_0_1px_hsl(var(--success))]"
      )}
    >
      {isWinner && (
        <div className="absolute right-3 top-3 z-10">
          <Badge variant="success">
            <Trophy className="h-3 w-3" />
            Recommended
          </Badge>
        </div>
      )}
      <CardContent className="flex flex-col gap-3 p-5">
        <div className="flex h-32 w-full items-center justify-center overflow-hidden rounded-lg bg-muted">
          {product.thumbnail ? (
            <img
              src={product.thumbnail}
              alt={product.title}
              className="h-full w-full object-contain p-3"
            />
          ) : (
            <Sparkles className="h-6 w-6 text-muted-foreground" />
          )}
        </div>

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {product.platform}
          </p>
          <h4 className="line-clamp-2 text-sm font-semibold leading-snug text-foreground">
            {product.title}
          </h4>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-lg font-bold text-foreground">
            {formatPrice(product.price, product.currency)}
          </span>
          {product.rating != null && (
            <span className="flex items-center gap-1 text-foreground">
              <Star className="h-3.5 w-3.5 fill-warning text-warning" />
              {product.rating.toFixed(1)}
            </span>
          )}
          {product.review_count != null && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <MessageSquareText className="h-3 w-3" />
              {product.review_count.toLocaleString()} reviews
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full", isWinner ? "bg-success" : "bg-primary/60")}
              style={{ width: `${Math.max(4, Math.min(100, score))}%` }}
            />
          </div>
          <span className="text-xs font-medium text-muted-foreground">
            {Math.round(score)}/100 value
          </span>
        </div>

        {features.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {features.map((feature) => (
              <Badge key={feature} variant="outline" className="font-normal">
                {feature}
              </Badge>
            ))}
          </div>
        )}

        <a
          href={product.link}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(buttonVariants({ variant: isWinner ? "default" : "outline", size: "sm" }))}
        >
          View product
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </CardContent>
    </Card>
  );
}
