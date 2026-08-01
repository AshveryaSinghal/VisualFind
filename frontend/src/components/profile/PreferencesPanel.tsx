import { useEffect, useState } from "react";
import { Layers, Save, ShoppingBag, SlidersHorizontal, Wallet } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/context/ToastContext";
import { ApiError } from "@/api/client";
import {
  useCategoryOptions,
  usePreferences,
  useUpdatePreferences,
} from "@/hooks/usePersonalization";
import { useTrustedPlatforms } from "@/hooks/useAnalytics";
import { SHOPPING_STYLE_OPTIONS } from "@/types";
import type { ShoppingStyle } from "@/types";
import { cn } from "@/utils/cn";

function Chip({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
        selected
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-transparent text-muted-foreground hover:border-primary/50 hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}

export function PreferencesPanel() {
  const { toast } = useToast();
  const { data: categories = [] } = useCategoryOptions();
  const { data: platforms = [] } = useTrustedPlatforms();
  const { data: preferences, isLoading } = usePreferences();
  const updatePreferences = useUpdatePreferences();

  const [favoriteCategories, setFavoriteCategories] = useState<string[]>([]);
  const [preferredPlatforms, setPreferredPlatforms] = useState<string[]>([]);
  const [budgetMin, setBudgetMin] = useState<string>("");
  const [budgetMax, setBudgetMax] = useState<string>("");
  const [shoppingStyle, setShoppingStyle] = useState<ShoppingStyle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!preferences) return;
    setFavoriteCategories(preferences.favorite_categories);
    setPreferredPlatforms(preferences.preferred_platforms);
    setBudgetMin(preferences.budget_min !== null ? String(preferences.budget_min) : "");
    setBudgetMax(preferences.budget_max !== null ? String(preferences.budget_max) : "");
    setShoppingStyle(preferences.shopping_style);
  }, [preferences]);

  function toggleCategory(value: string) {
    setFavoriteCategories((prev) =>
      prev.includes(value) ? prev.filter((c) => c !== value) : [...prev, value]
    );
  }

  function togglePlatform(value: string) {
    setPreferredPlatforms((prev) =>
      prev.includes(value) ? prev.filter((p) => p !== value) : [...prev, value]
    );
  }

  async function handleSave() {
    setError(null);
    const min = budgetMin.trim() ? Number(budgetMin) : null;
    const max = budgetMax.trim() ? Number(budgetMax) : null;

    if (min !== null && !Number.isFinite(min)) {
      setError("Minimum budget must be a number.");
      return;
    }
    if (max !== null && !Number.isFinite(max)) {
      setError("Maximum budget must be a number.");
      return;
    }

    try {
      await updatePreferences.mutateAsync({
        favorite_categories: favoriteCategories,
        preferred_platforms: preferredPlatforms,
        budget_min: min,
        budget_max: max,
        shopping_style: shoppingStyle,
      });
      toast({ variant: "success", title: "Preferences saved" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save your preferences.");
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            Favorite categories
          </CardTitle>
          <CardDescription>
            Used to surface "Trending in your favorite category" picks on the For You page.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {categories.map((category) => (
              <Chip
                key={category.value}
                selected={favoriteCategories.includes(category.value)}
                onClick={() => toggleCategory(category.value)}
              >
                {category.label}
              </Chip>
            ))}
            {categories.length === 0 && (
              <p className="text-sm text-muted-foreground">Loading categories…</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wallet className="h-4 w-4 text-primary" />
            Preferred budget
          </CardTitle>
          <CardDescription>
            Recommendations and alerts are gently filtered to stay within this range.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label htmlFor="budget_min" className="text-sm font-medium text-foreground">
                Minimum (₹)
              </label>
              <Input
                id="budget_min"
                type="number"
                min={0}
                placeholder="e.g. 500"
                value={budgetMin}
                onChange={(e) => setBudgetMin(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="budget_max" className="text-sm font-medium text-foreground">
                Maximum (₹)
              </label>
              <Input
                id="budget_max"
                type="number"
                min={0}
                placeholder="e.g. 5000"
                value={budgetMax}
                onChange={(e) => setBudgetMax(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShoppingBag className="h-4 w-4 text-primary" />
            Preferred shopping websites
          </CardTitle>
          <CardDescription>Platforms you'd like nudged to the top of recommendations.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {platforms.map((platform) => (
              <Chip
                key={platform}
                selected={preferredPlatforms.includes(platform)}
                onClick={() => togglePlatform(platform)}
              >
                {platform}
              </Chip>
            ))}
            {platforms.length === 0 && (
              <p className="text-sm text-muted-foreground">Loading platforms…</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            Shopping style
          </CardTitle>
          <CardDescription>How we should rank "you may also like" picks.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 sm:grid-cols-2">
            {SHOPPING_STYLE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setShoppingStyle(option.value)}
                aria-pressed={shoppingStyle === option.value}
                className={cn(
                  "rounded-lg border px-3 py-2.5 text-left text-sm transition-colors",
                  shoppingStyle === option.value
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/40"
                )}
              >
                <span className="flex items-center gap-2 font-medium text-foreground">
                  {option.label}
                  {shoppingStyle === option.value && <Badge className="ml-auto">Selected</Badge>}
                </span>
                <span className="text-xs text-muted-foreground">{option.description}</span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <Button onClick={handleSave} isLoading={updatePreferences.isPending || isLoading}>
        <Save className="h-4 w-4" />
        Save preferences
      </Button>
    </div>
  );
}
