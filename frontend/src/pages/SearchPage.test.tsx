import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { SearchPage } from "@/pages/SearchPage";
import { useImageSearch } from "@/hooks/useImageSearch";
import { SearchStoreProvider } from "@/context/SearchStoreContext";
import { ToastProvider } from "@/context/ToastContext";
import { AuthProvider } from "@/context/AuthContext";
import { CompareProvider } from "@/context/CompareContext";
import { SavedProductsProvider } from "@/context/SavedProductsContext";
import type { SearchResponse } from "@/types";

vi.mock("@/hooks/useImageSearch", () => ({
  useImageSearch: vi.fn(),
}));

const mockedUseImageSearch = vi.mocked(useImageSearch);

const responseWithMissingThumbnail: SearchResponse = {
  search_id: 1,
  best_guess_label: "Lip balm",
  product_query: "plum candy melts",
  total_matches_found: 1,
  trusted_matches_returned: 1,
  priced_count: 0,
  detected_brand: "Plum",
  brand_confidence: 0.9,
  official_domain: "plumgoodness.com",
  official_product_found: true,
  execution_time_ms: 100,
  from_cache: false,
  note: null,
  results: [
    {
      platform: "plum Official Store",
      title: "Plum Candy Melts Red Velvet Love Tinted Lip Balm",
      brand: "Plum",
      price: null,
      currency: null,
      link: "https://plumgoodness.com/product",
      source_domain: "plumgoodness.com",
      thumbnail: null,
      rating: null,
      review_count: null,
      price_source: null,
      extraction_method: null,
      confidence_score: 0.4,
      is_best_deal: false,
      savings: null,
      best_deal_reason: null,
      is_quick_commerce: false,
      delivery_estimate: null,
    },
  ],
} as unknown as SearchResponse;

function renderSearchPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToastProvider>
          <AuthProvider>
            <SearchStoreProvider>
              <CompareProvider>
                <SavedProductsProvider>
                  <SearchPage />
                </SavedProductsProvider>
              </CompareProvider>
            </SearchStoreProvider>
          </AuthProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("SearchPage", () => {
  beforeEach(() => {
    // jsdom doesn't implement the Blob URL APIs - stub them the way real
    // browsers behave (a unique token per call) so we can assert the
    // preview actually gets created and wired down to the result cards.
    let counter = 0;
    URL.createObjectURL = vi.fn(() => `blob:http://localhost/mock-${++counter}`);
    URL.revokeObjectURL = vi.fn();

    mockedUseImageSearch.mockReturnValue({
      search: vi.fn(),
      searchAsync: vi.fn(),
      data: responseWithMissingThumbnail,
      error: null,
      isPending: false,
      isError: false,
      isSuccess: true,
      uploadProgress: 0,
      reset: vi.fn(),
    } as unknown as ReturnType<typeof useImageSearch>);
  });

  it("uses the uploaded photo as a temporary placeholder for a result missing its own image", async () => {
    const user = userEvent.setup();
    const searchMock = vi.fn();
    mockedUseImageSearch.mockReturnValue({
      search: searchMock,
      searchAsync: vi.fn(),
      data: undefined,
      error: null,
      isPending: false,
      isError: false,
      isSuccess: false,
      uploadProgress: 0,
      reset: vi.fn(),
    } as unknown as ReturnType<typeof useImageSearch>);

    const { rerender } = renderSearchPage();

    // Before any result exists, the upload dropzone is what's on screen.
    const file = new File(["fake-bytes"], "lip-balm.jpg", { type: "image/jpeg" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    expect(searchMock).toHaveBeenCalledWith({ file });
    expect(URL.createObjectURL).toHaveBeenCalledWith(file);

    // Now simulate the mutation resolving with a result that has no image
    // of its own, the same way SearchPage picks up `data` from the hook.
    mockedUseImageSearch.mockReturnValue({
      search: searchMock,
      searchAsync: vi.fn(),
      data: responseWithMissingThumbnail,
      error: null,
      isPending: false,
      isError: false,
      isSuccess: true,
      uploadProgress: 100,
      reset: vi.fn(),
    } as unknown as ReturnType<typeof useImageSearch>);

    rerender(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <ToastProvider>
            <AuthProvider>
              <SearchStoreProvider>
                <CompareProvider>
                  <SavedProductsProvider>
                    <SearchPage />
                  </SavedProductsProvider>
                </CompareProvider>
              </SearchStoreProvider>
            </AuthProvider>
          </ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    const fallbackImg = await screen.findByAltText("Your uploaded reference photo");
    expect(fallbackImg.getAttribute("src")).toMatch(/^blob:http:\/\/localhost\/mock-\d+$/);
    expect(screen.getByText("Your photo")).toBeInTheDocument();
  });
});
