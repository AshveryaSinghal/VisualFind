import { motion } from "framer-motion";
import { Bot } from "lucide-react";

export function TypingIndicator() {
  return (
    <div className="flex items-end gap-2.5">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
        <Bot className="h-4 w-4" />
      </span>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-3">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-muted-foreground"
            animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
      </div>
    </div>
  );
}
