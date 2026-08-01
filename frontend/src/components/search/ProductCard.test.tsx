import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProductCard } from "@/components/search/ProductCard";
import { CompareProvider } from "@/context/CompareContext";
import { SavedProductsProvider } from "@/context/SavedProductsContext";
import { AuthProvider } from "@/context/AuthContext";
import type { PurchaseLink } from "@/types";

const product: PurchaseLink = {
  platform: "Flipkart",
  title: "Wireless Headphones XR-500",
  brand: "XR-500",
  price: "2499",
  currency: "INR",
  link: "https://flipkart.com/xr-500",
  source_domain: "flipkart.com",
  thumbnail: null,
  rating: 4.3,
  review_count: 1200,
  price_source: "google_shopping",
  extraction_method: null,
  confidence_score: 0.92,
  is_best_deal: true,
  savings: 300,
  best_deal_reason: "Chosen for its lowest price among trusted sellers.",
  is_quick_commerce: false,
  delivery_estimate: null,
};

function renderCard(
  overrides: Partial<PurchaseLink> = {},
  fallbackImage?: string | null,
  compactActions?: boolean
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuthProvider>
          <CompareProvider>
            <SavedProductsProvider>
              <ProductCard
                product={{ ...product, ...overrides }}
                fallbackImage={fallbackImage}
                compactActions={compactActions}
              />
            </SavedProductsProvider>
          </CompareProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ProductCard", () => {
  it("renders the product title, price and platform", () => {
    renderCard();
    expect(screen.getByText("Wireless Headphones XR-500")).toBeInTheDocument();
    expect(screen.getByText("₹2,499")).toBeInTheDocument();
    expect(screen.getByText("Flipkart")).toBeInTheDocument();
  });

  it("shows a best deal badge when is_best_deal is true", () => {
    renderCard({ is_best_deal: true });
    expect(screen.getByText("Best deal")).toBeInTheDocument();
  });

  it("shows a price-unavailable state instead of a fabricated price", () => {
    renderCard({ price: null, is_best_deal: false });
    expect(screen.getByText("Price unavailable")).toBeInTheDocument();
    expect(screen.getByText("Price not found")).toBeInTheDocument();
  });

  it("toggles the compare selection state when clicked", async () => {
    const user = userEvent.setup();
    renderCard();

    const compareButton = screen.getByRole("button", { name: "Add to comparison" });
    await user.click(compareButton);

    expect(screen.getByRole("button", { name: "Remove from comparison" })).toBeInTheDocument();
  });

  it("links to the product analytics page with the product's details", () => {
    renderCard();

    const analyticsButton = screen.getByRole("button", {
      name: "View analytics for Wireless Headphones XR-500",
    });
    expect(analyticsButton).toBeInTheDocument();
  });

  it("does not toggle compare when the card itself is clicked", async () => {
    const user = userEvent.setup();
    renderCard();

    await user.click(screen.getByText("Wireless Headphones XR-500"));

    expect(screen.getByRole("button", { name: "Add to comparison" })).toBeInTheDocument();
  });

  it("shows a placeholder icon when there is no thumbnail and no fallback image", () => {
    renderCard({ thumbnail: null });
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("falls back to the searched photo when the result has no product image", () => {
    renderCard({ thumbnail: null }, "blob:http://localhost/fake-preview");

    const img = screen.getByAltText("Your uploaded reference photo");
    expect(img).toHaveAttribute("src", "blob:http://localhost/fake-preview");
    expect(screen.getByText("Your photo")).toBeInTheDocument();
  });

  it("prefers the real product thumbnail over the fallback image when both are present", () => {
    renderCard({ thumbnail: "https://example.com/real.jpg" }, "blob:http://localhost/fake-preview");

    const img = screen.getByAltText("Wireless Headphones XR-500");
    expect(img).toHaveAttribute("src", "https://example.com/real.jpg");
  });

  it("shows Compare/Analytics labels alongside their icons by default", () => {
    renderCard();

    expect(screen.getByText("Compare")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
  });

  it("shows the View product label alongside its icon on the primary link button", () => {
    renderCard();

    expect(screen.getByText("View product")).toBeInTheDocument();
  });

  it("hides the Compare/Analytics labels and keeps only icons when compactActions is set", () => {
    renderCard({}, undefined, true);

    expect(screen.queryByText("Compare")).not.toBeInTheDocument();
    expect(screen.queryByText("Analytics")).not.toBeInTheDocument();
    // Buttons are still present and accessible via their aria-labels, icon-only.
    expect(screen.getByRole("button", { name: "Add to comparison" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "View analytics for Wireless Headphones XR-500" })
    ).toBeInTheDocument();
  });
});
