import { useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ExternalLink, Star, Store, LineChart, MessageSquareText, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { PriceHistoryChart } from "@/components/product-analytics/PriceHistoryChart";
import { SentimentBars } from "@/components/product-analytics/SentimentBars";
import { QuickSummaryCard } from "@/components/product-analytics/QuickSummaryCard";
import { ProductAnalyticsSkeleton } from "@/components/product-analytics/ProductAnalyticsSkeleton";
import { PriceAlertButton } from "@/components/product-analytics/PriceAlertButton";
import { SaveButton } from "@/components/common/SaveButton";
import { useProductAnalytics } from "@/hooks/useProductAnalytics";
import { parseProductAnalyticsSearch } from "@/utils/productAnalyticsLink";
import { formatPrice } from "@/utils/format";
import { cn } from "@/utils/cn";

export function ProductAnalyticsPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const query = useMemo(() => parseProductAnalyticsSearch(searchParams), [searchParams]);
  const link = searchParams.get("link");

  const { data, isLoading, isError, error, refetch } = useProductAnalytics(query);

  return (
    <div className="container py-10">
      <PageHeader
        eyebrow="Product analytics"
        title={query?.title ?? "Product analytics"}
        description="Price trend, review sentiment, and a quick take - at a glance."
        action={
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
        }
      />

      <div className="mt-8">
        {!query && (
          <ErrorState
            error={new Error("Open this page by clicking a product from your search results.")}
          />
        )}

        {query && isLoading && <ProductAnalyticsSkeleton />}

        {query && isError && <ErrorState error={error} onRetry={() => refetch()} />}

        {query && data && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="space-y-6"
          >
            {}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border bg-muted sm:h-20 sm:w-20">
                  {data.thumbnail ? (
                    <img src={data.thumbnail} alt={data.product_name} className="h-full w-full object-contain p-2" />
                  ) : (
                    <Store className="h-7 w-7 text-muted-foreground" />
                  )}
                </div>
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {data.platform && <Badge variant="secondary">{data.platform}</Badge>}
                    {data.rating !== null && data.rating !== undefined && (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Star className="h-3.5 w-3.5 fill-warning text-warning" />
                        {data.rating.toFixed(1)}
                        {data.review_count ? ` (${data.review_count.toLocaleString()})` : ""}
                      </span>
                    )}
                  </div>
                  <p className="text-xl font-bold tracking-tight text-foreground">
                    {formatPrice(data.current_price, data.currency)}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {link && (
                  <a
                    href={link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                  >
                    View product
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
                <PriceAlertButton
                  productName={data.product_name}
                  platform={data.platform}
                  currency={data.currency}
                  thumbnail={data.thumbnail}
                  link={link}
                  currentPrice={data.current_price}
                />
                <SaveButton
                  variant="full"
                  className="w-auto"
                  product={{
                    title: data.product_name,
                    platform: data.platform,
                    price: data.current_price,
                    currency: data.currency,
                    thumbnail: data.thumbnail,
                    link,
                    rating: data.rating,
                    review_count: data.review_count,
                  }}
                />
              </div>
            </div>

            {}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <CardHeader className="flex-row items-center gap-2 space-y-0">
                  <LineChart className="h-4 w-4 text-primary" />
                  <CardTitle className="text-base">Price history</CardTitle>
                </CardHeader>
                <CardContent>
                  <PriceHistoryChart
                    points={data.price_points}
                    currency={data.currency}
                    direction={data.price_direction}
                    changePercent={data.price_change_percent}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex-row items-center gap-2 space-y-0">
                  <MessageSquareText className="h-4 w-4 text-primary" />
                  <CardTitle className="text-base">Review sentiment</CardTitle>
                </CardHeader>
                <CardContent>
                  <SentimentBars sentiment={data.sentiment} />
                </CardContent>
              </Card>
            </div>

            {}
            <Card>
              <CardHeader className="flex-row items-center gap-2 space-y-0">
                <Sparkles className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Quick summary</CardTitle>
              </CardHeader>
              <CardContent>
                <QuickSummaryCard summary={data.summary} verdict={data.verdict} />
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>
    </div>
  );
}
