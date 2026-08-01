import { test, expect } from "@playwright/test";

/**
 * Covers the "Describe What You Need" journey: a chat turn that returns
 * status=ready with a structured query, followed by the search call and
 * a recommendation card backed by a real (mocked) purchase link. This is
 * the same two-call contract described in README.md#ai-shopping-assistant-v3
 * (/api/ai/chat then /api/ai/search) - the test exists to catch a frontend
 * regression that breaks that handoff, not to re-test Gemini itself.
 */

const MOCK_CHAT_READY = {
  status: "ready",
  assistant_message:
    "Got it — looking for budget-friendly gym headphones. Searching trusted platforms now.",
  structured_query: {
    category: "headphones",
    budget_max: 2000,
    budget_currency: "INR",
    brand: null,
    preferences: ["gym", "sweat-resistant"],
    search_text: "gym headphones under 2000 rupees",
  },
};

const MOCK_AI_SEARCH_RESPONSE = {
  search: {
    search_id: 202,
    best_guess_label: "Sweat-resistant gym headphones",
    product_query: "gym headphones under 2000 rupees",
    total_matches_found: 4,
    trusted_matches_returned: 1,
    priced_count: 1,
    detected_brand: null,
    brand_confidence: null,
    official_domain: null,
    official_product_found: false,
    execution_time_ms: 2100,
    from_cache: false,
    note: null,
    results: [
      {
        platform: "Amazon",
        title: "JBL Endurance Run Gym Headphones",
        price: "1499",
        currency: "INR",
        link: "https://www.amazon.in/example-headphones",
        source_domain: "amazon.in",
        thumbnail: "https://via.placeholder.com/200",
        rating: 4.4,
        review_count: 3021,
        price_source: "google_shopping",
        extraction_method: "serpapi_google_shopping",
        confidence_score: 0.95,
        is_best_deal: true,
        savings: 300,
      },
    ],
  },
  recommendation: {
    product: {
      platform: "Amazon",
      title: "JBL Endurance Run Gym Headphones",
      price: "1499",
      currency: "INR",
      link: "https://www.amazon.in/example-headphones",
      source_domain: "amazon.in",
      thumbnail: "https://via.placeholder.com/200",
      rating: 4.4,
      review_count: 3021,
      price_source: "google_shopping",
      extraction_method: "serpapi_google_shopping",
      confidence_score: 0.95,
      is_best_deal: true,
      savings: 300,
    },
    reason: "Best sweat-resistance in budget with the highest review count of the trusted matches.",
    why_it_matches: "Under your ₹2000 budget and built for gym use.",
    money_saved: 300,
    is_official_store: false,
    alternatives: [],
  },
};

test.describe("AI shopping assistant journey", () => {
  test("a conversational query returns a recommendation backed by a real purchase link", async ({
    page,
  }) => {
    await page.route("**/api/ai/chat", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_CHAT_READY),
      })
    );
    await page.route("**/api/ai/search", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_AI_SEARCH_RESPONSE),
      })
    );

    await page.goto("/assistant");
    await expect(
      page.getByRole("heading", { name: /tell me what you need/i })
    ).toBeVisible();

    await page.getByPlaceholder(/tell the ai what you need/i).fill("I need headphones for the gym.");
    await page.getByRole("button", { name: /send message/i }).click();

    // Assistant's reply for this turn.
    await expect(page.getByText(/searching trusted platforms now/i)).toBeVisible({
      timeout: 10_000,
    });

    // Recommendation card, backed by the mocked /api/ai/search response.
    await expect(page.getByText(/jbl endurance run gym headphones/i).first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText(/highest review count of the trusted matches/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /buy now/i })).toHaveAttribute(
      "href",
      "https://www.amazon.in/example-headphones"
    );
  });

  test("a 503 when Gemini isn't configured surfaces a clear, actionable error", async ({ page }) => {
    await page.route("**/api/ai/chat", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "The AI shopping assistant isn't configured on this deployment.",
        }),
      })
    );

    await page.goto("/assistant");
    await page.getByPlaceholder(/tell the ai what you need/i).fill("Find me a laptop.");
    await page.getByRole("button", { name: /send message/i }).click();

    await expect(page.getByText(/isn't configured on this deployment/i)).toBeVisible({
      timeout: 10_000,
    });
  });
});
