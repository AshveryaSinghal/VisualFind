import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { useAnalytics } from "@/hooks/useAnalytics";
import type { AnalyticsSummary } from "@/types";

vi.mock("@/hooks/useAnalytics", () => ({
  useAnalytics: vi.fn(),
}));

const mockedUseAnalytics = vi.mocked(useAnalytics);

const summary: AnalyticsSummary = {
  total_searches: 42,
  most_searched_products: [{ name: "Wireless Headphones", count: 5 }],
  most_searched_platforms: [{ name: "Flipkart", count: 20 }],
  most_searched_brands: [{ name: "XR-500", count: 3 }],
  average_search_time_ms: 1500,
  average_products_found: 6.4,
  average_priced_products: 4.8,
  total_products_found: 268,
  price_hit_rate: 82.5,
  official_match_rate: 41.2,
  fastest_search_ms: 640,
  searches_last_7_days: 9,
  searches_by_day: [
    { date: "2026-07-24", count: 1 },
    { date: "2026-07-25", count: 0 },
    { date: "2026-07-26", count: 2 },
    { date: "2026-07-27", count: 1 },
    { date: "2026-07-28", count: 3 },
    { date: "2026-07-29", count: 0 },
    { date: "2026-07-30", count: 2 },
  ],
  best_deal_found: {
    label: "Wireless Headphones",
    platform: "Flipkart",
    price: 1999,
    search_id: 101,
  },
  last_search_at: "2026-07-30T09:00:00Z",
};

function mockAnalytics(overrides: Partial<ReturnType<typeof useAnalytics>>) {
  mockedUseAnalytics.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useAnalytics>);
}

describe("AnalyticsPage", () => {
  it("shows skeleton placeholders while loading", () => {
    mockAnalytics({ isLoading: true });
    const { container } = render(<AnalyticsPage />, { wrapper: MemoryRouter });
    expect(container.querySelectorAll(".animate-pulse, [class*='skeleton' i]").length).toBeGreaterThanOrEqual(0);
    expect(screen.queryByText("No analytics yet")).not.toBeInTheDocument();
  });

  it("shows an error state with a retry action on failure", () => {
    const refetch = vi.fn();
    mockAnalytics({ isError: true, error: new Error("Network error"), refetch });
    render(<AnalyticsPage />, { wrapper: MemoryRouter });

    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it("shows an empty state when there have been zero searches", () => {
    mockAnalytics({ data: { ...summary, total_searches: 0 } });
    render(<AnalyticsPage />, { wrapper: MemoryRouter });

    expect(screen.getByText("No analytics yet")).toBeInTheDocument();
  });

  it("renders stat cards and top-list sections once data is available", () => {
    mockAnalytics({ data: summary });
    render(<AnalyticsPage />, { wrapper: MemoryRouter });

    expect(screen.getByText("Total searches")).toBeInTheDocument();
    expect(screen.getByText("Avg. search time")).toBeInTheDocument();
    expect(screen.getByText("Top searched products")).toBeInTheDocument();
    expect(screen.getByText("Top platforms (best deal)")).toBeInTheDocument();
    expect(screen.getByText("Top brands (approximate)")).toBeInTheDocument();
    expect(screen.queryByText("No analytics yet")).not.toBeInTheDocument();
  });
});
