import { motion } from "framer-motion";
import { ScanSearch, ShieldCheck, Layers, Gauge } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent } from "@/components/ui/card";

const PIPELINE_STAGES = [
  {
    title: "Image understanding",
    description:
      "Your photo is uploaded and analyzed with Google Lens to identify the product and generate candidate purchase links.",
  },
  {
    title: "Trust filtering",
    description:
      "Every candidate link is checked against a curated allowlist of retailers with real buyer protection — anything else is dropped.",
  },
  {
    title: "Live price extraction",
    description:
      "A multi-tier pipeline (Google Shopping, JSON-LD, OpenGraph, rendered DOM) resolves a real, current price and currency for each match.",
  },
  {
    title: "Ranking & best deal",
    description:
      "Results are deduplicated, normalized, and sorted so the cheapest genuine match is always surfaced with a savings estimate.",
  },
];

export function AboutPage() {
  return (
    <div className="container py-10">
      <PageHeader
        eyebrow="How it works"
        title="About VisualFind"
        description="A visual product search tool built to find real prices on real, trusted retailers — nothing fabricated, nothing scraped from sketchy sources."
      />

      <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-4">
          {PIPELINE_STAGES.map((stage, index) => (
            <motion.div
              key={stage.title}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.35, delay: index * 0.06 }}
            >
              <Card>
                <CardContent className="flex gap-4 p-5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                    {index + 1}
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">{stage.title}</h3>
                    <p className="mt-1.5 text-sm text-muted-foreground">{stage.description}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        <div className="space-y-5">
          <Card>
            <CardContent className="space-y-4 p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <ShieldCheck className="h-4 w-4 text-primary" />
                Why an allowlist, not a scam classifier
              </div>
              <p className="text-sm text-muted-foreground">
                Detecting fraudulent listings with a classifier is an open-ended, hard-to-verify
                problem. Restricting results to a curated list of retailers with real return
                policies is simpler, safer, and never wrong in a way that surprises you.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="space-y-4 p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Layers className="h-4 w-4 text-primary" />
                Multi-tier extraction
              </div>
              <p className="text-sm text-muted-foreground">
                Cheaper, more reliable sources are always tried first; the pipeline only pays for
                a slower rendered-page scrape when nothing faster answered the question.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="space-y-4 p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Gauge className="h-4 w-4 text-primary" />
                Confidence, not guesswork
              </div>
              <p className="text-sm text-muted-foreground">
                Every price shows a confidence score reflecting how it was extracted — so you can
                tell a licensed Google Shopping price apart from a best-effort DOM scrape.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="mt-16 flex items-center justify-center gap-2 text-sm text-muted-foreground">
        <ScanSearch className="h-4 w-4" />
        VisualFind — built on FastAPI, SerpApi, and React.
      </div>
    </div>
  );
}
