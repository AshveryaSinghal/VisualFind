import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ImageUp,
  Tag,
  ScanSearch,
  Building2,
  ShieldCheck,
  Layers,
  Scale,
  Sparkles,
  Check,
} from "lucide-react";
import type { SearchResponse } from "@/types";
import { cn } from "@/utils/cn";

interface Stage {
  key: string;
  icon: typeof ImageUp;
  label: string;
}

const STAGES: Stage[] = [
  { key: "upload", icon: ImageUp, label: "Image uploaded" },
  { key: "brand", icon: Tag, label: "Brand detected" },
  { key: "lens", icon: ScanSearch, label: "Searching Google Lens" },
  { key: "official", icon: Building2, label: "Searching official store" },
  { key: "retailers", icon: ShieldCheck, label: "Searching trusted retailers" },
  { key: "matching", icon: Layers, label: "Matching products" },
  { key: "pricing", icon: Scale, label: "Comparing prices" },
  { key: "recommend", icon: Sparkles, label: "Building recommendation" },
];

interface LiveTimelineProps {
  mode: "live";
  uploadDone: boolean;
}

interface SummaryTimelineProps {
  mode: "summary";
  response: SearchResponse;
}

type SearchTimelineProps = LiveTimelineProps | SummaryTimelineProps;

export function SearchTimeline(props: SearchTimelineProps) {
  const [liveIndex, setLiveIndex] = useState(0);
  const uploadDone = props.mode === "live" ? props.uploadDone : true;

  useEffect(() => {
    if (props.mode !== "live") return;
    if (!uploadDone) {
      setLiveIndex(0);
      return;
    }
    const interval = setInterval(() => {
      setLiveIndex((prev) => (prev < STAGES.length - 1 ? prev + 1 : prev));
    }, 900);
    return () => clearInterval(interval);
  }, [props.mode, uploadDone]);

  const getState = (index: number): "done" | "active" | "pending" => {
    if (props.mode === "live") {
      if (!props.uploadDone) return index === 0 ? "active" : "pending";
      if (index < liveIndex) return "done";
      if (index === liveIndex) return "active";
      return "pending";
    }

    const { response } = props;
    switch (STAGES[index].key) {
      case "upload":
        return "done";
      case "brand":
        return response.detected_brand ? "done" : "pending";
      case "lens":
        return response.total_matches_found > 0 ? "done" : "pending";
      case "official":
        return response.official_product_found ? "done" : "pending";
      case "retailers":
        return response.trusted_matches_returned > 0 ? "done" : "pending";
      case "matching":
        return response.trusted_matches_returned > 0 ? "done" : "pending";
      case "pricing":
        return response.priced_count > 0 ? "done" : "pending";
      case "recommend":
        return response.results.some((r) => r.is_best_deal) ? "done" : "pending";
      default:
        return "pending";
    }
  };

  return (
    <div
      className={cn(
        "grid gap-3",
        props.mode === "live" ? "grid-cols-1" : "grid-cols-2 sm:grid-cols-4"
      )}
    >
      {STAGES.map((stage, index) => {
        const state = getState(index);
        return (
          <motion.div
            key={stage.key}
            animate={{ opacity: state === "pending" ? 0.4 : 1 }}
            className={cn(
              "flex items-center gap-3 rounded-lg border border-border bg-card/50 px-4 py-3",
              props.mode === "summary" && "flex-col text-center gap-2 py-4"
            )}
          >
            <span
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                state === "done" && "bg-success/15 text-success",
                state === "active" && "bg-primary/15 text-primary",
                state === "pending" && "bg-muted text-muted-foreground"
              )}
            >
              {state === "done" ? (
                <Check className="h-4 w-4" />
              ) : (
                <stage.icon className={cn("h-4 w-4", state === "active" && "animate-pulse")} />
              )}
            </span>
            <span
              className={cn(
                "text-sm text-foreground",
                props.mode === "summary" && "text-xs text-muted-foreground"
              )}
            >
              {stage.label}
            </span>
          </motion.div>
        );
      })}
    </div>
  );
}
