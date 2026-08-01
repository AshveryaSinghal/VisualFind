import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { runAISearch, sendChatTurn } from "@/services/aiService";
import type { AISearchResponse, ChatMessage } from "@/types";
import { queryKeys } from "@/hooks/queryKeys";

export type AssistantPhase = "idle" | "chatting" | "thinking" | "searching" | "done" | "error";

interface DisplayMessage extends ChatMessage {
  id: number;
}

let idCounter = 0;
const nextId = () => ++idCounter;

interface AssistantChatContextValue {
  messages: DisplayMessage[];
  phase: AssistantPhase;
  error: string | null;
  searchResult: AISearchResponse | null;
  sendMessage: (text: string) => Promise<void>;
  reset: () => void;
  isBusy: boolean;
}

const AssistantChatContext = createContext<AssistantChatContextValue | undefined>(undefined);

/** Owns the actual conversation state at the app level (see App.tsx), not
 * inside AssistantPage - local component state gets wiped whenever the
 * route unmounts (e.g. leaving /assistant to check something on /saved),
 * which was silently discarding the whole conversation + result on return.
 * This survives navigation for the whole app session, and is only cleared
 * by an explicit "New conversation" action or a full page reload. */
export function AssistantChatProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [phase, setPhase] = useState<AssistantPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<AISearchResponse | null>(null);
  const transcriptRef = useRef<ChatMessage[]>([]);

  const runSearch = useCallback(
    async (structuredQuery: NonNullable<Awaited<ReturnType<typeof sendChatTurn>>["structured_query"]>) => {
      setPhase("searching");
      try {
        const result = await runAISearch(structuredQuery);
        setSearchResult(result);
        setPhase("done");
        queryClient.invalidateQueries({ queryKey: queryKeys.analytics });
        queryClient.invalidateQueries({ queryKey: ["history"] });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Search failed. Please try again.");
        setPhase("error");
      }
    },
    [queryClient]
  );

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      setError(null);
      const userMessage: DisplayMessage = { id: nextId(), role: "user", content: trimmed };
      setMessages((prev) => [...prev, userMessage]);
      transcriptRef.current = [...transcriptRef.current, { role: "user", content: trimmed }];
      setPhase("thinking");

      try {
        const reply = await sendChatTurn(transcriptRef.current);
        const assistantMessage: DisplayMessage = {
          id: nextId(),
          role: "assistant",
          content: reply.assistant_message,
        };
        setMessages((prev) => [...prev, assistantMessage]);
        transcriptRef.current = [
          ...transcriptRef.current,
          { role: "assistant", content: reply.assistant_message },
        ];

        if (reply.status === "ready" && reply.structured_query) {
          await runSearch(reply.structured_query);
        } else {
          setPhase("chatting");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "The AI assistant is unavailable right now.");
        setPhase("error");
      }
    },
    [runSearch]
  );

  const reset = useCallback(() => {
    setMessages([]);
    transcriptRef.current = [];
    setPhase("idle");
    setError(null);
    setSearchResult(null);
  }, []);

  const value = useMemo<AssistantChatContextValue>(
    () => ({
      messages,
      phase,
      error,
      searchResult,
      sendMessage,
      reset,
      isBusy: phase === "thinking" || phase === "searching",
    }),
    [messages, phase, error, searchResult, sendMessage, reset]
  );

  return <AssistantChatContext.Provider value={value}>{children}</AssistantChatContext.Provider>;
}

export function useAssistantChatContext(): AssistantChatContextValue {
  const ctx = useContext(AssistantChatContext);
  if (!ctx) throw new Error("useAssistantChatContext must be used within an AssistantChatProvider");
  return ctx;
}
