import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { X, Wand2, AlertTriangle } from "lucide-react";
import type { ComparePreferences, PurchaseLink, SmartCompareResponse } from "@/types";
import { compareProducts } from "@/services/aiService";
import { ApiError } from "@/api/client";
import { CompareQuestionnaire } from "@/components/compare/CompareQuestionnaire";
import { CompareResult } from "@/components/compare/CompareResult";
import { Button } from "@/components/ui/button";

interface SmartCompareDialogProps {
  open: boolean;
  onClose: () => void;
  productA: PurchaseLink | null;
  productB: PurchaseLink | null;
}

type Step = "questions" | "loading" | "result" | "error";

export function SmartCompareDialog({ open, onClose, productA, productB }: SmartCompareDialogProps) {
  const [step, setStep] = useState<Step>("questions");
  const [preferences, setPreferences] = useState<ComparePreferences | null>(null);
  const [result, setResult] = useState<SmartCompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setStep("questions");
      setPreferences(null);
      setResult(null);
      setError(null);
    }
  }, [open, productA, productB]);

  useEffect(() => {
    if (!open) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEscape);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!productA || !productB) return null;

  async function handleSubmit(prefs: ComparePreferences) {
    setPreferences(prefs);
    setStep("loading");
    setError(null);
    try {
      const response = await compareProducts({
        product_a: productA!,
        product_b: productB!,
        ...prefs,
      });
      setResult(response);
      setStep("result");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Something went wrong comparing these products.";
      setError(message);
      setStep("error");
    }
  }

  function handleStartOver() {
    setStep("questions");
    setResult(null);
    setError(null);
  }

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-background/85 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 12 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
            className="relative z-[101] flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <div className="flex items-center gap-2">
                <Wand2 className="h-4 w-4 text-primary" />
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    AI-powered product comparison
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    A personalized verdict, not just a spec sheet.
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                aria-label="Close comparison"
                className="rounded-md p-2 text-muted-foreground transition hover:bg-accent hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="overflow-auto p-6">
              {(step === "questions" || step === "loading") && (
                <CompareQuestionnaire
                  productA={productA}
                  productB={productB}
                  onSubmit={handleSubmit}
                  isSubmitting={step === "loading"}
                />
              )}

              {step === "error" && (
                <div className="flex flex-col items-center gap-4 py-10 text-center">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                    <AlertTriangle className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="font-medium text-foreground">Couldn't complete the comparison</p>
                    <p className="mt-1 text-sm text-muted-foreground">{error}</p>
                  </div>
                  <Button onClick={() => preferences && handleSubmit(preferences)}>
                    Try again
                  </Button>
                </div>
              )}

              {step === "result" && result && preferences && (
                <CompareResult
                  productA={productA}
                  productB={productB}
                  preferences={preferences}
                  result={result}
                  onStartOver={handleStartOver}
                />
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}
