import { useEffect, useState } from "react";
import { apiClient } from "@/api/client";
import { cn } from "@/utils/cn";
import { Tooltip } from "@/components/ui/tooltip";

type Status = "checking" | "online" | "offline";

export function BackendStatusDot({ className }: { className?: string }) {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        await apiClient.get("/health", { timeout: 5000 });
        if (!cancelled) setStatus("online");
      } catch {
        if (!cancelled) setStatus("offline");
      }
    }

    check();
    const interval = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const label =
    status === "checking"
      ? "Checking backend connection…"
      : status === "online"
      ? "Backend connected"
      : "Backend unreachable";

  return (
    <Tooltip content={label}>
      <span className={cn("relative flex h-2 w-2", className)}>
        {status === "online" && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
        )}
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            status === "checking" && "bg-muted-foreground",
            status === "online" && "bg-success",
            status === "offline" && "bg-destructive"
          )}
        />
      </span>
    </Tooltip>
  );
}
