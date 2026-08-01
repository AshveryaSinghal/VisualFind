import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SentimentBars } from "./SentimentBars";
import type { ReviewSentiment } from "@/types";

const estimatedSentiment: ReviewSentiment = {
  positive_pct: 70,
  neutral_pct: 20,
  negative_pct: 10,
  basis: "Estimated from a 4.2-star average rating",
  is_estimate: true,
  review_count_analyzed: null,
  sample_positive: null,
  sample_negative: null,
};

const realSentiment: ReviewSentiment = {
  positive_pct: 82,
  neutral_pct: 12,
  negative_pct: 6,
  basis: "Based on 128 analyzed reviews",
  is_estimate: false,
  review_count_analyzed: 128,
  sample_positive: "Great quality and fast shipping.",
  sample_negative: "Runs a bit small for the price.",
};

describe("SentimentBars", () => {
  it("renders an empty state when sentiment is null", () => {
    render(<SentimentBars sentiment={null} />);
    expect(screen.getByText("No rating data for this listing")).toBeInTheDocument();
  });

  it("shows the 'Estimated from rating' badge for estimated sentiment", () => {
    render(<SentimentBars sentiment={estimatedSentiment} />);
    expect(screen.getByText("Estimated from rating")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
    expect(screen.getByText("20%")).toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
  });

  it("shows the 'Real review analysis' badge and sample quotes for real sentiment", () => {
    render(<SentimentBars sentiment={realSentiment} />);
    expect(screen.getByText("Real review analysis")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText(/Great quality and fast shipping\./)).toBeInTheDocument();
    expect(screen.getByText(/Runs a bit small for the price\./)).toBeInTheDocument();
  });

  it("does not show sample quotes when sentiment is estimated", () => {
    render(<SentimentBars sentiment={estimatedSentiment} />);
    expect(screen.queryByText(/Positive review:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Negative review:/)).not.toBeInTheDocument();
  });
});
