import { useState } from "react";
import { Trash2, History as HistoryIcon, LayoutGrid, List } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { HistoryTable } from "@/components/history/HistoryTable";
import { HistoryCardGrid } from "@/components/history/HistoryCardGrid";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  useClearHistory,
  useDeleteHistoryItem,
  useSearchHistory,
} from "@/hooks/useSearchHistory";
import { useToast } from "@/context/ToastContext";

export function HistoryPage() {
  const { data, isLoading, isError, error, refetch } = useSearchHistory(100);
  const deleteMutation = useDeleteHistoryItem();
  const clearMutation = useClearHistory();
  const { toast } = useToast();
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null);
  const [view, setView] = useState<"cards" | "table">("cards");

  const handleDelete = (id: number) => {
    setPendingDeleteId(id);
    deleteMutation.mutate(id, {
      onSuccess: () => toast({ variant: "success", title: "Search removed from history" }),
      onError: (err) =>
        toast({
          variant: "error",
          title: "Couldn't delete search",
          description: err instanceof Error ? err.message : undefined,
        }),
      onSettled: () => setPendingDeleteId(null),
    });
  };

  const handleClearAll = () => {
    clearMutation.mutate(undefined, {
      onSuccess: () => {
        toast({ variant: "success", title: "History cleared" });
        setConfirmClearOpen(false);
      },
      onError: (err) =>
        toast({
          variant: "error",
          title: "Couldn't clear history",
          description: err instanceof Error ? err.message : undefined,
        }),
    });
  };

  return (
    <div className="container py-10">
      <PageHeader
        eyebrow="Your activity"
        title="Search history"
        description="Every image search you've run, with quick access back to full results."
        action={
          data &&
          data.length > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex items-center rounded-md border border-border p-0.5">
                <button
                  onClick={() => setView("cards")}
                  aria-label="Card view"
                  aria-pressed={view === "cards"}
                  className={`rounded-sm p-1.5 transition-colors ${
                    view === "cards"
                      ? "bg-accent text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <LayoutGrid className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setView("table")}
                  aria-label="Table view"
                  aria-pressed={view === "table"}
                  className={`rounded-sm p-1.5 transition-colors ${
                    view === "table"
                      ? "bg-accent text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <List className="h-4 w-4" />
                </button>
              </div>
              <Button
                variant="outline"
                onClick={() => setConfirmClearOpen(true)}
                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
                Clear history
              </Button>
            </div>
          )
        }
      />

      <div className="mt-8">
        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-14 w-full rounded-lg" />
            ))}
          </div>
        )}

        {isError && <ErrorState error={error} onRetry={() => refetch()} />}

        {data && data.length === 0 && (
          <EmptyState
            icon={HistoryIcon}
            title="No searches yet"
            description="Run your first visual search and it'll show up here."
          />
        )}

        {data && data.length > 0 && view === "cards" && (
          <HistoryCardGrid
            items={data}
            onDelete={handleDelete}
            isDeleting={deleteMutation.isPending}
            pendingDeleteId={pendingDeleteId}
          />
        )}

        {data && data.length > 0 && view === "table" && (
          <HistoryTable
            items={data}
            onDelete={handleDelete}
            isDeleting={deleteMutation.isPending}
            pendingDeleteId={pendingDeleteId}
          />
        )}
      </div>

      <Dialog open={confirmClearOpen} onOpenChange={setConfirmClearOpen}>
        <DialogHeader>
          <DialogTitle>Clear all search history?</DialogTitle>
          <DialogDescription>
            This permanently deletes every search record. This action can't be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setConfirmClearOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleClearAll}
            isLoading={clearMutation.isPending}
          >
            Clear everything
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
