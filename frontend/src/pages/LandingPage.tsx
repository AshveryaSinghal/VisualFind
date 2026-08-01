import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight,
  ImagePlus,
  MessageSquareText,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Clock,
  Zap,
  BadgeCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useTrustedPlatforms } from "@/hooks/useAnalytics";
import { useSearchHistory } from "@/hooks/useSearchHistory";
import { useRecommendations } from "@/hooks/usePersonalization";
import { useAuth } from "@/context/AuthContext";
import { useSearchStore } from "@/context/SearchStoreContext";
import { ProductCard } from "@/components/search/ProductCard";
import { formatRelativeDate } from "@/utils/format";

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Trusted platforms only",
    description:
      "Every result is filtered through a curated allowlist of retailers with real buyer protection — never a random scam link.",
  },
  {
    icon: Zap,
    title: "Live, multi-tier pricing",
    description:
      "A seven-stage extraction pipeline pulls real-time prices from Google Shopping, JSON-LD, and rendered pages — never stale data.",
  },
  {
    icon: BadgeCheck,
    title: "Automatic best-deal detection",
    description:
      "Results are normalized, deduplicated, and sorted so the cheapest genuine match is always surfaced first.",
  },
];

export function LandingPage() {
  const navigate = useNavigate();
  const { setPendingFile } = useSearchStore();
  const { isAuthenticated } = useAuth();
  const { data: platforms, isLoading: platformsLoading } = useTrustedPlatforms();
  const { data: history } = useSearchHistory(4);
  const { data: recommendations } = useRecommendations();

  const topPicks = recommendations?.items.slice(0, 2) ?? [];

  const handleImageInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setPendingFile(file);
    navigate("/search");
  };

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-grid-pattern bg-[size:48px_48px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,black,transparent)]" />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[36rem] w-[36rem] -translate-x-1/2 rounded-full bg-primary/20 blur-[120px]" />

      <section className="container relative pb-16 pt-20 sm:pt-28">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mx-auto max-w-2xl text-center"
        >
          <Badge variant="outline" className="mb-5 border-primary/30 text-primary">
            <Sparkles className="h-3 w-3" />
            Now with an AI Shopping Assistant
          </Badge>
          <h1 className="text-balance text-4xl font-extrabold tracking-tight text-foreground sm:text-6xl">
            Find it. Or just describe it.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-balance text-base text-muted-foreground sm:text-lg">
            Upload any product photo, or tell the AI what you need in plain language.
            VisualFind checks live prices across trusted platforms and recommends the best
            real deal — so you never overpay or land on a scam site.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mx-auto mt-10 grid max-w-3xl grid-cols-1 gap-5 sm:grid-cols-2"
        >
          <Card className="group flex flex-col justify-between overflow-hidden border-border/80 p-1 transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-lg">
            <CardContent className="flex flex-1 flex-col p-7">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <ImagePlus className="h-6 w-6" />
              </div>
              <h2 className="text-xl font-bold text-foreground">Search by Image</h2>
              <p className="mt-2 flex-1 text-sm text-muted-foreground">
                Upload a photo to identify products and compare real prices instantly.
              </p>
              <label className="mt-6">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={handleImageInputChange}
                />
                <span
                  role="button"
                  className="inline-flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90"
                >
                  Upload Image
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </label>
            </CardContent>
          </Card>

          <Card className="group flex flex-col justify-between overflow-hidden border-primary/30 bg-gradient-to-br from-primary/5 via-card to-card p-1 transition-all hover:-translate-y-1 hover:border-primary/50 hover:shadow-lg">
            <CardContent className="flex flex-1 flex-col p-7">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <MessageSquareText className="h-6 w-6" />
              </div>
              <h2 className="text-xl font-bold text-foreground">Describe What You Need</h2>
              <p className="mt-2 flex-1 text-sm text-muted-foreground">
                Tell the AI your budget, preferences, and requirements — it asks a couple of
                quick questions, then finds and recommends the best real match.
              </p>
              <Button className="mt-6 h-11 w-full" onClick={() => navigate("/assistant")}>
                Start with AI
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        <div className="mt-5 flex items-center justify-center gap-3 text-sm text-muted-foreground">
          <span>or</span>
          <Button variant="link" className="h-auto p-0" onClick={() => navigate("/search")}>
            go to the classic search page
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </section>

      {isAuthenticated && topPicks.length > 0 && (
        <section className="container relative pb-16">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="mx-auto max-w-3xl rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card p-6 shadow-sm"
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
                  Picked for you
                </h2>
              </div>
              <Button variant="link" className="h-auto p-0 text-sm" onClick={() => navigate("/recommendations")}>
                See all
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {topPicks.map((item, index) => (
                <div key={`${item.product.link}-${index}`} className="space-y-2">
                  <p className="truncate text-xs font-medium text-muted-foreground">{item.reason_text}</p>
                  <ProductCard product={item.product} index={index} hideCompareToggle />
                </div>
              ))}
            </div>
          </motion.div>
        </section>
      )}

      <section className="container relative pb-24">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
          {FEATURES.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.4, delay: index * 0.08 }}
            >
              <Card className="h-full">
                <CardContent className="p-6">
                  <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <feature.icon className="h-5 w-5" />
                  </div>
                  <h3 className="font-semibold text-foreground">{feature.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="container relative pb-24">
        <div className="mb-6 flex items-center gap-2">
          <ScanSearch className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Trusted platforms
          </h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {platformsLoading &&
            Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-8 w-24 rounded-full" />
            ))}
          {platforms?.map((platform) => (
            <Badge key={platform} variant="secondary" className="px-3 py-1.5 text-sm">
              {platform}
            </Badge>
          ))}
        </div>
      </section>

      {history && history.length > 0 && (
        <section className="container relative pb-28">
          <div className="mb-6 flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Recent searches
            </h2>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {history.map((item) => (
              <Card
                key={item.id}
                className="cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-lg"
                onClick={() => navigate(`/results/${item.id}`)}
              >
                <CardContent className="p-5">
                  <p className="truncate font-medium text-foreground">
                    {item.best_guess_label ?? item.product_query ?? "Untitled search"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {item.filtered_count} trusted matches · {formatRelativeDate(item.created_at)}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
