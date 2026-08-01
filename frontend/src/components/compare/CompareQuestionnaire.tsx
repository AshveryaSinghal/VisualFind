import { useState, type FormEvent } from "react";
import { Wallet, Target, Tag, Scale, Sparkles, ArrowRight } from "lucide-react";
import type { ComparePreferences, ComparePriority, PurchaseLink } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/cn";

interface CompareQuestionnaireProps {
  productA: PurchaseLink;
  productB: PurchaseLink;
  onSubmit: (preferences: ComparePreferences) => void;
  isSubmitting?: boolean;
}

const PURPOSE_SUGGESTIONS = [
  "Daily / everyday use",
  "Gift for someone",
  "Professional / work use",
  "Travel",
  "Gaming or heavy use",
];

export function CompareQuestionnaire({
  productA,
  productB,
  onSubmit,
  isSubmitting,
}: CompareQuestionnaireProps) {
  const [budget, setBudget] = useState("");
  const [mainPurpose, setMainPurpose] = useState("");
  const [preferredBrand, setPreferredBrand] = useState("");
  const [priority, setPriority] = useState<ComparePriority>("quality");
  const [specialPreferences, setSpecialPreferences] = useState("");
  const [touched, setTouched] = useState(false);

  const currency = productA.currency || productB.currency || "INR";
  const purposeIsValid = mainPurpose.trim().length > 0;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!purposeIsValid) return;

    onSubmit({
      budget: budget.trim() ? Number(budget) : null,
      budget_currency: currency,
      main_purpose: mainPurpose.trim(),
      preferred_brand: preferredBrand.trim() || null,
      priority,
      special_preferences: specialPreferences.trim() || null,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="rounded-xl border border-border bg-muted/40 p-4">
        <p className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Sparkles className="h-4 w-4 text-primary" />
          Tell us a bit about what you need
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          We'll use this to personalize the comparison between{" "}
          <span className="font-medium text-foreground">{productA.title}</span> and{" "}
          <span className="font-medium text-foreground">{productB.title}</span> — not just line
          up their specs.
        </p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-1.5">
          <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <Wallet className="h-3.5 w-3.5 text-primary" />
            Budget <span className="font-normal text-muted-foreground">(optional)</span>
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
              {currency}
            </span>
            <Input
              type="number"
              min={0}
              inputMode="decimal"
              placeholder="e.g. 15000"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="pl-14"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <Tag className="h-3.5 w-3.5 text-primary" />
            Preferred brand <span className="font-normal text-muted-foreground">(optional)</span>
          </label>
          <Input
            placeholder="e.g. Sony, no preference"
            value={preferredBrand}
            onChange={(e) => setPreferredBrand(e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Target className="h-3.5 w-3.5 text-primary" />
          What's this mainly for?
        </label>
        <Input
          placeholder="e.g. daily commute, gaming, gifting my dad"
          value={mainPurpose}
          onChange={(e) => setMainPurpose(e.target.value)}
        />
        {touched && !purposeIsValid && (
          <p className="text-xs text-destructive">Let us know what you'll mainly use it for.</p>
        )}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {PURPOSE_SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => setMainPurpose(suggestion)}
              className={cn(
                "rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition hover:border-primary/40 hover:bg-accent hover:text-foreground",
                mainPurpose === suggestion && "border-primary/60 bg-primary/10 text-primary"
              )}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Scale className="h-3.5 w-3.5 text-primary" />
          Is price or quality more important to you?
        </label>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setPriority("price")}
            className={cn(
              "rounded-xl border border-border p-3 text-left transition hover:border-primary/40",
              priority === "price" && "border-primary bg-primary/10"
            )}
          >
            <span className="text-sm font-medium text-foreground">Price</span>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Get the best deal, even if it means fewer features.
            </p>
          </button>
          <button
            type="button"
            onClick={() => setPriority("quality")}
            className={cn(
              "rounded-xl border border-border p-3 text-left transition hover:border-primary/40",
              priority === "quality" && "border-primary bg-primary/10"
            )}
          >
            <span className="text-sm font-medium text-foreground">Quality</span>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Get the better/more reliable option, even if pricier.
            </p>
          </button>
        </div>
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          Any special preferences?{" "}
          <span className="font-normal text-muted-foreground">(optional)</span>
        </label>
        <textarea
          value={specialPreferences}
          onChange={(e) => setSpecialPreferences(e.target.value)}
          placeholder="e.g. needs long battery life, must be lightweight, eco-friendly packaging…"
          rows={3}
          className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:border-ring disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>

      <Button type="submit" isLoading={isSubmitting} className="w-full sm:w-auto sm:self-end">
        {isSubmitting ? "Comparing…" : "Compare these two products"}
        {!isSubmitting && <ArrowRight className="h-4 w-4" />}
      </Button>
    </form>
  );
}
