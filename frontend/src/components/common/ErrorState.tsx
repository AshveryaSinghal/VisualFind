import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/api/client";
import { cn } from "@/utils/cn";

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ error, onRetry, className }: ErrorStateProps) {
  const isNetworkError = error instanceof ApiError && error.status === null;
  const message =
    error instanceof Error ? error.message : "Something went wrong. Please try again.";

  const Icon = isNetworkError ? WifiOff : AlertTriangle;

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-16 text-center",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
        <Icon className="h-6 w-6 text-destructive" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">
          {isNetworkError ? "Can't reach the backend" : "Something went wrong"}
        </p>
        <p className="max-w-md text-sm text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-1">
          <RefreshCw className="h-3.5 w-3.5" />
          Try again
        </Button>
      )}
    </div>
  );
}
