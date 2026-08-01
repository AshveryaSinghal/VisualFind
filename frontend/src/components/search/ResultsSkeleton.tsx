import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function ResultsSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, index) => (
        <Card key={index} className="overflow-hidden">
          <Skeleton className="aspect-square w-full rounded-none" />
          <div className="space-y-3 p-4">
            <Skeleton className="h-5 w-20 rounded-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-9 w-full rounded-md" />
          </div>
        </Card>
      ))}
    </div>
  );
}
