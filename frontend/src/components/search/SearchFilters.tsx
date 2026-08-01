import { SlidersHorizontal, X, Search } from "lucide-react";
import type { ResultFilters } from "@/components/search/useResultFilters";
import { SORT_OPTIONS } from "@/types";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/cn";

interface SearchFiltersProps {
  filters: ResultFilters;
  onChange: (filters: ResultFilters) => void;
  availablePlatforms: string[];
  onReset: () => void;
  resultCount: number;
}

const STORE_TYPE_OPTIONS: { value: ResultFilters["storeType"]; label: string }[] = [
  { value: "all", label: "All stores" },
  { value: "official", label: "Official store" },
  { value: "marketplace", label: "Marketplace" },
  { value: "quick_commerce", label: "Quick delivery" },
];

export function SearchFilters({
  filters,
  onChange,
  availablePlatforms,
  onReset,
  resultCount,
}: SearchFiltersProps) {
  const update = <K extends keyof ResultFilters>(key: K, value: ResultFilters[K]) => {
    onChange({ ...filters, [key]: value });
  };

  const togglePlatform = (platform: string) => {
    const next = filters.platforms.includes(platform)
      ? filters.platforms.filter((p) => p !== platform)
      : [...filters.platforms, platform];
    update("platforms", next);
  };

  const hasActiveFilters =
    filters.query ||
    filters.storeType !== "all" ||
    filters.platforms.length > 0 ||
    filters.pricedOnly ||
    filters.minPrice ||
    filters.maxPrice;

  return (
    <div className="space-y-5 rounded-xl border border-border bg-card/50 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <SlidersHorizontal className="h-4 w-4" />
          Filters
        </div>
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={onReset} className="h-7 px-2 text-xs">
            <X className="h-3 w-3" />
            Reset
          </Button>
        )}
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={filters.query}
          onChange={(event) => update("query", event.target.value)}
          placeholder="Search within results…"
          className="pl-9"
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground">Sort by</label>
        <Select
          value={filters.sortBy}
          onValueChange={(value) => update("sortBy", value as ResultFilters["sortBy"])}
          options={SORT_OPTIONS}
        />
      </div>

      <Separator />

      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">Store type</label>
        <div className="flex flex-wrap gap-1.5">
          {STORE_TYPE_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => update("storeType", option.value)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                filters.storeType === option.value
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {availablePlatforms.length > 0 && (
        <>
          <Separator />
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">Platform</label>
            <div className="flex flex-wrap gap-1.5">
              {availablePlatforms.map((platform) => {
                const active = filters.platforms.includes(platform);
                return (
                  <button
                    key={platform}
                    onClick={() => togglePlatform(platform)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                      active
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border text-muted-foreground hover:bg-accent hover:text-foreground"
                    )}
                  >
                    {platform}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}

      <Separator />

      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">Price range</label>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            inputMode="decimal"
            placeholder="Min"
            value={filters.minPrice}
            onChange={(event) => update("minPrice", event.target.value)}
          />
          <span className="text-muted-foreground">–</span>
          <Input
            type="number"
            inputMode="decimal"
            placeholder="Max"
            value={filters.maxPrice}
            onChange={(event) => update("maxPrice", event.target.value)}
          />
        </div>
      </div>

      <Separator />

      <label className="flex cursor-pointer items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">Priced items only</span>
        <input
          type="checkbox"
          checked={filters.pricedOnly}
          onChange={(event) => update("pricedOnly", event.target.checked)}
          className="h-4 w-4 rounded border-input accent-primary"
        />
      </label>

      <div className="pt-1 text-xs text-muted-foreground">
        Showing <span className="font-medium text-foreground">{resultCount}</span> result
        {resultCount === 1 ? "" : "s"}
      </div>

      {filters.platforms.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {filters.platforms.map((platform) => (
            <Badge key={platform} variant="secondary" className="gap-1">
              {platform}
              <button onClick={() => togglePlatform(platform)} aria-label={`Remove ${platform} filter`}>
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
