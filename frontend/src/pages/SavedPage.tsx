import { Bookmark } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { SavedProductCard } from "@/components/common/SavedProductCard";
import { useSavedProducts, useUnsaveProduct } from "@/hooks/usePersonalization";
import { useToast } from "@/context/ToastContext";

export function SavedPage() {
  const { data, isLoading, isError, error, refetch } = useSavedProducts();
  const unsaveMutation = useUnsaveProduct();
  const { toast } = useToast();

  const handleRemove = (id: number) => {
    unsaveMutation.mutate(id, {
      onSuccess: () => toast({ variant: "success", title: "Removed from saved" }),
      onError: (err) =>
        toast({
          variant: "error",
          title: "Couldn't remove this product",
          description: err instanceof Error ? err.message : undefined,
        }),
    });
  };

  return (
    <div className="container py-10">
      <PageHeader
        eyebrow="Your list"
        title="Saved for later"
        description="Products you've bookmarked to come back to - tap the bookmark icon on any product to add or remove it."
      />

      <div className="mt-8">
        {isLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="aspect-square w-full rounded-xl" />
            ))}
          </div>
        )}

        {isError && <ErrorState error={error} onRetry={() => refetch()} />}

        {data && data.length === 0 && (
          <EmptyState
            icon={Bookmark}
            title="Nothing saved yet"
            description="Tap the bookmark icon on a product card or its analytics page to save it here."
          />
        )}

        {data && data.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data.map((item) => (
              <SavedProductCard
                key={item.id}
                item={item}
                onRemove={handleRemove}
                isRemoving={unsaveMutation.isPending && unsaveMutation.variables === item.id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
