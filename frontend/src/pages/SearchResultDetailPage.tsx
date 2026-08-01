import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { SearchResultsView } from "@/components/search/SearchResultsView";
import { ResultsSkeleton } from "@/components/search/ResultsSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { Button } from "@/components/ui/button";
import { useSearchDetail } from "@/hooks/useSearchHistory";

export function SearchResultDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const searchId = id ? Number(id) : null;
  const isValidId = searchId !== null && Number.isFinite(searchId);

  const { data, isLoading, isError, error, refetch } = useSearchDetail(
    isValidId ? searchId : null
  );

  return (
    <div className="container py-10">
      <PageHeader
        eyebrow="Search history"
        title={data?.best_guess_label ?? data?.product_query ?? "Search results"}
        description={`Search #${searchId ?? "—"}`}
        action={
          <Button variant="outline" onClick={() => navigate("/history")}>
            <ArrowLeft className="h-4 w-4" />
            Back to history
          </Button>
        }
      />

      <div className="mt-8">
        {!isValidId && (
          <ErrorState error={new Error("That search ID isn't valid.")} />
        )}
        {isValidId && isLoading && <ResultsSkeleton />}
        {isValidId && isError && <ErrorState error={error} onRetry={() => refetch()} />}
        {isValidId && data && <SearchResultsView response={data} />}
      </div>
    </div>
  );
}
