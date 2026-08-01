import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/utils/cn";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
  className?: string;
  /** Extra classes for the tooltip's own positioning wrapper (the element
   * that actually participates in a parent flex/grid layout). Needed
   * whenever the wrapped child relies on flex sizing (e.g. `flex-1`) from
   * its grandparent, since that sizing has to live on this wrapper. */
  wrapperClassName?: string;
}

export function Tooltip({ content, children, side = "top", className, wrapperClassName }: TooltipProps) {
  const [visible, setVisible] = useState(false);

  return (
    <span
      className={cn("relative inline-flex", wrapperClassName)}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      <AnimatePresence>
        {visible && (
          <motion.span
            initial={{ opacity: 0, y: side === "top" ? 4 : -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            role="tooltip"
            className={cn(
              "pointer-events-none absolute left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-popover px-2.5 py-1 text-xs text-popover-foreground shadow-md",
              side === "top" ? "bottom-full mb-2" : "top-full mt-2",
              className
            )}
          >
            {content}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}
