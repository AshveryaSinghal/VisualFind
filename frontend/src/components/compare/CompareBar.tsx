import { AnimatePresence, motion } from "framer-motion";
import { Scale, X } from "lucide-react";
import { useCompare, MAX_COMPARE_ITEMS } from "@/context/CompareContext";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";

export function CompareBar() {
  const { items, remove, clear, open, isOpen } = useCompare();

  if (isOpen) return null;

  return (
    <AnimatePresence>
      {items.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 40 }}
          transition={{ type: "spring", stiffness: 380, damping: 32 }}
          className="fixed inset-x-0 bottom-4 z-40 flex justify-center px-4"
        >
          <div className="flex w-full max-w-2xl flex-wrap items-center gap-3 rounded-2xl border border-border bg-card/95 px-4 py-3 shadow-2xl backdrop-blur">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Scale className="h-4 w-4 text-primary" />
              {items.length} of {MAX_COMPARE_ITEMS} selected
            </div>

            <div className="flex flex-1 items-center gap-1.5 overflow-x-auto">
              {items.map((item) => (
                <Tooltip key={`${item.platform}-${item.link}`} content={item.title}>
                  <button
                    onClick={() => remove(item)}
                    className="flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive"
                  >
                    <span className="max-w-[6rem] truncate">{item.platform}</span>
                    <X className="h-3 w-3" />
                  </button>
                </Tooltip>
              ))}
            </div>

            <div className="ml-auto flex shrink-0 items-center gap-2">
              <Button variant="ghost" size="sm" onClick={clear}>
                Clear
              </Button>
              <Button size="sm" onClick={open} disabled={items.length < 2}>
                Compare
              </Button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
