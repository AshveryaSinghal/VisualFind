/**
 * Thin re-export over AssistantChatContext. Kept as its own hook/module
 * (rather than inlining useAssistantChatContext directly in
 * AssistantPage.tsx) so AssistantPage.test.tsx's existing
 * `vi.mock("@/hooks/useAIChat")` keeps working unchanged - the actual
 * state now lives in the context (see AssistantChatContext.tsx) so it
 * survives navigating away from /assistant and back, but the public shape
 * consumed by AssistantPage is unchanged.
 */
import { useAssistantChatContext } from "@/context/AssistantChatContext";

export function useAIChat() {
  return useAssistantChatContext();
}
