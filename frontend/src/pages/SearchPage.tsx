import { useEffect, useRef } from "react";
import { RotateCcw, AlertCircle } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { UploadDropzone } from "@/components/upload/UploadDropzone";
import { SearchProgress } from "@/components/search/SearchProgress";
import { SearchResultsView } from "@/components/search/SearchResultsView";
import { ErrorState } from "@/components/common/ErrorState";
import { Button } from "@/components/ui/button";
import { useImageSearch } from "@/hooks/useImageSearch";
import { useSearchStore } from "@/context/SearchStoreContext";
import { useToast } from "@/context/ToastContext";

export function SearchPage() {
  const { search, data, error, isPending, isError, reset, uploadProgress } = useImageSearch();
  const {
    pendingFile,
    setPendingFile,
    lastSearchResult,
    lastSearchError,
    setLastSearchResult,
    setLastSearchError,
    clearLastSearch,
    queryImagePreviewUrl,
    setQueryImagePreviewFile,
  } = useSearchStore();
  const { toast } = useToast();
  const consumedPendingFile = useRef(false);

  useEffect(() => {
    if (pendingFile && !consumedPendingFile.current) {
      consumedPendingFile.current = true;
      setQueryImagePreviewFile(pendingFile);
      search({ file: pendingFile });
      setPendingFile(null);
    }
  }, [pendingFile, search, setPendingFile, setQueryImagePreviewFile]);

  // Mirror this mutation's outcome into the persisted context - this is
  // what makes results survive navigating away from /search and back
  // (e.g. to check whether something is Saved) instead of vanishing on
  // remount, since local mutation state doesn't outlive the component.
  useEffect(() => {
    if (data) setLastSearchResult(data);
  }, [data, setLastSearchResult]);

  useEffect(() => {
    if (isError) {
      const message = error instanceof Error ? error.message : "Search failed. Please try again.";
      setLastSearchError(message);
      toast({ variant: "error", title: "Search failed", description: message });
    }
  }, [isError, error, setLastSearchError, toast]);

  const handleFileSelected = (file: File) => {
    setQueryImagePreviewFile(file);
    search({ file });
  };

  const handleNewSearch = () => {
    reset();
    clearLastSearch();
  };

  // Treat an unconsumed pendingFile (set by AssistantPage/LandingPage,
  // about to trigger a fresh search) as pending too, so there's no
  // one-frame flash of a stale persisted result before the effect above
  // kicks the new search off.
  const effectivePending = isPending || Boolean(pendingFile);

  // Prefer this mount's own mutation result while a search is actively
  // resolving; otherwise fall back to whatever was last persisted, which
  // is what makes a returning visit show the previous result immediately.
  const displayData = data ?? lastSearchResult;
  const displayErrorMessage = isError
    ? error instanceof Error
      ? error.message
      : "Search failed. Please try again."
    : !displayData
      ? lastSearchError
      : null;

  return (
    <div className="container py-10">
      <PageHeader
        eyebrow="Visual search"
        title="Find where to buy it — for less"
        description="Upload a clear photo of the product. VisualFind checks live prices across every trusted platform in one pass."
        action={
          (displayData || displayErrorMessage) && (
            <Button variant="outline" onClick={handleNewSearch}>
              <RotateCcw className="h-4 w-4" />
              Search something new
            </Button>
          )
        }
      />

      <div className="mt-8">
        {!displayData && !effectivePending && !displayErrorMessage && (
          <div className="mx-auto max-w-2xl">
            <UploadDropzone onFileSelected={handleFileSelected} />
          </div>
        )}

        {effectivePending && <SearchProgress uploadProgress={uploadProgress} />}

        {displayErrorMessage && !effectivePending && (
          <ErrorState
            error={new Error(displayErrorMessage)}
            onRetry={handleNewSearch}
            className="mx-auto max-w-2xl"
          />
        )}

        {displayData && !effectivePending && (
          <>
            {displayData.note && (
              <div className="mb-6 flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {displayData.note}
              </div>
            )}
            <SearchResultsView response={displayData} fallbackImage={queryImagePreviewUrl} />
          </>
        )}
      </div>
    </div>
  );
}
