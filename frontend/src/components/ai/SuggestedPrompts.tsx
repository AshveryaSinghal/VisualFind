import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { SUGGESTED_PROMPTS } from "@/types";

interface SuggestedPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

export function SuggestedPrompts({ onSelect, disabled }: SuggestedPromptsProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5 text-primary" />
        Try asking
      </div>
      <div className="flex flex-wrap gap-2">
        {SUGGESTED_PROMPTS.map((prompt, index) => (
          <motion.button
            key={prompt}
            type="button"
            disabled={disabled}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            onClick={() => onSelect(prompt)}
            className="rounded-full border border-border bg-card px-3.5 py-1.5 text-sm text-foreground transition-colors hover:border-primary/50 hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
          >
            {prompt}
          </motion.button>
        ))}
      </div>
    </div>
  );
}
