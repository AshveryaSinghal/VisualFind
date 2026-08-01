import { useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import type { HistoryItem } from "@/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { HistoryCard } from "@/components/history/HistoryCard";
import { useHistoryFilters } from "@/hooks/useHistoryFilters";

const PAGE_SIZE = 12;

interface HistoryCardGridProps {
  items: HistoryItem[];
  onDelete: (id: number) => void;
  isDeleting: boolean;
  pendingDeleteId?: number | null;
}

export function HistoryCardGrid({
  items,
  onDelete,
  isDeleting,
  pendingDeleteId = null,
}: HistoryCardGridProps) {
  const { query, setQuery, officialOnly, setOfficialOnly, filtered } = useHistoryFilters(items);
  const [page, setPage] = useState(0);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const paginated = filtered.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
            placeholder="Search history…"
            className="pl-9"
          />
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={officialOnly}
            onChange={(event) => {
              setOfficialOnly(event.target.checked);
              setPage(0);
            }}
            className="h-4 w-4 rounded border-input accent-primary"
          />
          Official listings only
        </label>
      </div>

      {paginated.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border py-12 text-center text-sm text-muted-foreground">
          No searches match your filters.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {paginated.map((item, index) => (
            <HistoryCard
              key={item.id}
              item={item}
              index={index}
              onDelete={onDelete}
              isDeleting={isDeleting && pendingDeleteId === item.id}
            />
          ))}
        </div>
      )}

      {filtered.length > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Page {currentPage + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages - 1}
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
