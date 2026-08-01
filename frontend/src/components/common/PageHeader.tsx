import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/utils/cn";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function PageHeader({ eyebrow, title, description, action, className }: PageHeaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={cn(
        "flex flex-col gap-4 border-b border-border pb-8 sm:flex-row sm:items-end sm:justify-between",
        className
      )}
    >
      <div className="space-y-2">
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">{eyebrow}</p>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{title}</h1>
        {description && (
          <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </motion.div>
  );
}
