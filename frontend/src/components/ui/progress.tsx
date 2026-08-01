import { cn } from "@/utils/cn";

interface ProgressProps {
  value: number;
  className?: string;
  indicatorClassName?: string;
}

export function Progress({ value, className, indicatorClassName }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-secondary", className)}
    >
      <div
        className={cn("h-full rounded-full bg-primary transition-all duration-300 ease-out", indicatorClassName)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
