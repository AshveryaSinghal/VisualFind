import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";
import { cn } from "@/utils/cn";
import type { ChatRole } from "@/types";

interface ChatBubbleProps {
  role: ChatRole;
  content: string;

  animate?: boolean;
}

const CHARS_PER_TICK = 2;
const TICK_MS = 16;

export function ChatBubble({ role, content, animate = false }: ChatBubbleProps) {
  const isUser = role === "user";
  const [displayed, setDisplayed] = useState(animate ? "" : content);
  const indexRef = useRef(0);

  useEffect(() => {
    if (!animate) {
      setDisplayed(content);
      return;
    }
    indexRef.current = 0;
    setDisplayed("");
    const interval = setInterval(() => {
      indexRef.current += CHARS_PER_TICK;
      setDisplayed(content.slice(0, indexRef.current));
      if (indexRef.current >= content.length) {
        clearInterval(interval);
      }
    }, TICK_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn("flex items-end gap-2.5", isUser && "flex-row-reverse")}
    >
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-secondary text-secondary-foreground" : "bg-primary/15 text-primary"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
          isUser
            ? "rounded-br-sm bg-primary text-primary-foreground"
            : "rounded-bl-sm border border-border bg-card text-card-foreground"
        )}
      >
        {displayed}
        {animate && displayed.length < content.length && (
          <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-current align-middle" />
        )}
      </div>
    </motion.div>
  );
}
