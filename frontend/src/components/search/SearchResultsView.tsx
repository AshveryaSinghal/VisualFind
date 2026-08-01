import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { SearchResponse } from "@/types";
import { SearchSummaryBar } from "@/components/search/SearchSummaryBar";
import { SearchFilters } from "@/components/search/SearchFilters";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { SearchTimeline } from "@/components/search/SearchTimeline";
import { useResultFilters } from "@/components/search/useResultFilters";
import { EmptyState } from "@/components/common/EmptyState";
import { PackageSearch } from "lucide-react";
import { cn } from "@/utils/cn";

function PipelineDisclosure({ response }: { response: SearchResponse }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-border">
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between px-5 py-3 text-sm font-medium text-foreground"
        aria-expanded={open}
      >
        How VisualFind found this
        <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-border p-5">
          <SearchTimeline mode="summary" response={response} />
        </div>
      )}
    </div>
  );
}

interface SearchResultsViewProps {
  response: SearchResponse;
  /** Tab-local object URL for the searched photo, used only as a display
   * fallback for result cards missing a product image. */
  fallbackImage?: string | null;
}

export function SearchResultsView({ response, fallbackImage }: SearchResultsViewProps) {
  const { filters, setFilters, filtered, availablePlatforms, resetFilters } = useResultFilters(
    response.results
  );

  if (response.results.length === 0) {
    return (
      <div className="space-y-6">
        <SearchSummaryBar response={response} />
        <PipelineDisclosure response={response} />
        <EmptyState
          icon={PackageSearch}
          title="No trusted matches found"
          description={
            response.note ??
            "We couldn't find this product on any of our trusted platforms. Try a clearer photo or a different angle."
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SearchSummaryBar response={response} />
      <PipelineDisclosure response={response} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[16rem_1fr]">
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <SearchFilters
            filters={filters}
            onChange={setFilters}
            availablePlatforms={availablePlatforms}
            onReset={resetFilters}
            resultCount={filtered.length}
          />
        </aside>
        <ResultsGrid results={filtered} fallbackImage={fallbackImage} />
      </div>
    </div>
  );
}
