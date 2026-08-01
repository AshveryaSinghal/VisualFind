import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { AlertCircle, RotateCcw, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { Button } from "@/components/ui/button";
import { ChatBubble } from "@/components/ai/ChatBubble";
import { ChatInput } from "@/components/ai/ChatInput";
import { TypingIndicator } from "@/components/ai/TypingIndicator";
import { SuggestedPrompts } from "@/components/ai/SuggestedPrompts";
import { RecommendationCard } from "@/components/ai/RecommendationCard";
import { SmartSearchBar } from "@/components/search/SmartSearchBar";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { useAIChat } from "@/hooks/useAIChat";
import { useSearchStore } from "@/context/SearchStoreContext";
import { useToast } from "@/context/ToastContext";

export function AssistantPage() {
  const navigate = useNavigate();
  const { setPendingFile } = useSearchStore();
  const { toast } = useToast();
  const { messages, phase, error, searchResult, sendMessage, reset, isBusy } = useAIChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, phase]);

  useEffect(() => {
    if (phase === "error" && error) {
      toast({ variant: "error", title: "AI assistant error", description: error });
    }
  }, [phase, error, toast]);

  const handleImageSelected = (file: File) => {
    setPendingFile(file);
    navigate("/search");
  };

  const hasStarted = messages.length > 0;

  return (
    <>
      <div className="container max-w-3xl py-10">
        <PageHeader
          eyebrow="AI Shopping Assistant"
          title="Tell me what you need — I'll find the best real deal"
          description="Describe your needs in plain language. The assistant asks a couple of quick questions, then searches live prices across trusted platforms and recommends one best product."
          action={
            hasStarted && (
              <Button variant="outline" onClick={reset}>
                <RotateCcw className="h-4 w-4" />
                New conversation
              </Button>
            )
          }
        />

        <div className="mt-8 space-y-6">
          {!hasStarted && (
            <div className="space-y-8">
              <SmartSearchBar onTextSearch={sendMessage} onImageSelected={handleImageSelected} />
              <SuggestedPrompts onSelect={sendMessage} />
            </div>
          )}

          {hasStarted && (
            <>
              <div
                ref={scrollRef}
                className="flex max-h-[28rem] flex-col gap-4 overflow-y-auto rounded-2xl border border-border bg-background/40 p-4 sm:p-6"
              >
                <AnimatePresence initial={false}>
                  {messages.map((message, index) => (
                    <ChatBubble
                      key={message.id}
                      role={message.role}
                      content={message.content}
                      animate={message.role === "assistant" && index === messages.length - 1}
                    />
                  ))}
                </AnimatePresence>
                {phase === "thinking" && <TypingIndicator />}
              </div>

              {phase !== "done" && phase !== "error" && (
                <ChatInput
                  onSend={sendMessage}
                  disabled={isBusy}
                  placeholder={
                    phase === "searching"
                      ? "Searching trusted platforms for the best match…"
                      : "Type your reply…"
                  }
                />
              )}

              {phase === "searching" && (
                <div className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3.5 text-sm text-primary">
                  <Sparkles className="h-4 w-4 animate-pulse" />
                  Searching Google Shopping, official brand stores, and trusted platforms for real
                  prices…
                </div>
              )}

              {phase === "error" && error && (
                <ErrorState error={new Error(error)} onRetry={reset} />
              )}
            </>
          )}

          {phase === "done" && searchResult && (
            <div className="space-y-8 pt-2">
              {searchResult.search.note && (
                <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-warning">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  {searchResult.search.note}
                </div>
              )}

              {searchResult.recommendation?.product && (
                <RecommendationCard recommendation={searchResult.recommendation} />
              )}
            </div>
          )}
        </div>
      </div>

      {phase === "done" && searchResult && searchResult.search.results.length > 0 && (
        <div className="container max-w-5xl pb-10">
          <div className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              All matching results
            </h2>
            <ResultsGrid results={searchResult.search.results} />
          </div>
        </div>
      )}
    </>
  );
}
