import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AssistantPage } from "@/pages/AssistantPage";
import { useAIChat } from "@/hooks/useAIChat";
import { SearchStoreProvider } from "@/context/SearchStoreContext";
import { ToastProvider } from "@/context/ToastContext";

vi.mock("@/hooks/useAIChat", () => ({
  useAIChat: vi.fn(),
}));

const mockedUseAIChat = vi.mocked(useAIChat);

function baseChatState(overrides: Partial<ReturnType<typeof useAIChat>> = {}) {
  return {
    messages: [],
    phase: "idle",
    error: null,
    searchResult: null,
    sendMessage: vi.fn(),
    reset: vi.fn(),
    isBusy: false,
    ...overrides,
  } as unknown as ReturnType<typeof useAIChat>;
}

function renderAssistant() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <SearchStoreProvider>
          <AssistantPage />
        </SearchStoreProvider>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("AssistantPage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the search bar and suggested prompts before a conversation starts", () => {
    mockedUseAIChat.mockReturnValue(baseChatState());
    renderAssistant();

    expect(
      screen.getByText(/Tell me what you need — I'll find the best real deal/i)
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /new conversation/i })).not.toBeInTheDocument();
  });

  it("shows the chat transcript and a way to start over once a conversation has messages", () => {
    mockedUseAIChat.mockReturnValue(
      baseChatState({
        messages: [
          { id: 1, role: "user", content: "I need running shoes under 3000 rupees" },
          { id: 2, role: "assistant", content: "Got it — any preferred brand?" },
        ],
        phase: "chatting",
      })
    );
    renderAssistant();

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByText("I need running shoes under 3000 rupees")).toBeInTheDocument();
    expect(screen.getByText("Got it — any preferred brand?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new conversation/i })).toBeInTheDocument();
  });

  it("shows an error state with a retry option when the assistant errors out", () => {
    mockedUseAIChat.mockReturnValue(
      baseChatState({
        messages: [{ id: 1, role: "user", content: "Find me a laptop" }],
        phase: "error",
        error: "The assistant is temporarily unavailable.",
      })
    );
    renderAssistant();

    expect(screen.getAllByText(/temporarily unavailable/i).length).toBeGreaterThan(0);
  });
});
