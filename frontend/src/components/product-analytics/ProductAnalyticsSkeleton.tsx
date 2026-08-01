import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function ProductAnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Skeleton className="h-20 w-20 shrink-0 rounded-xl" />
        <div className="w-full space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <Skeleton className="h-4 w-32" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-56 w-full rounded-lg" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <Skeleton className="h-4 w-28" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-full" />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-36" />
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-6 w-40 rounded-full" />
        </CardContent>
      </Card>
    </div>
  );
}
