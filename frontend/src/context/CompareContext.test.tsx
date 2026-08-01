import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import type { ReactNode } from "react";
import { CompareProvider, useCompare, MAX_COMPARE_ITEMS } from "@/context/CompareContext";
import type { PurchaseLink } from "@/types";

function makeProduct(overrides: Partial<PurchaseLink> = {}): PurchaseLink {
  return {
    platform: "Amazon",
    title: "Test product",
    brand: null,
    price: "999",
    currency: "INR",
    link: "https://example.com/product",
    source_domain: "example.com",
    thumbnail: null,
    rating: null,
    review_count: null,
    price_source: null,
    extraction_method: null,
    confidence_score: null,
    is_best_deal: false,
    savings: null,
    best_deal_reason: null,
    is_quick_commerce: false,
    delivery_estimate: null,
    ...overrides,
  };
}

const wrapper = ({ children }: { children: ReactNode }) => (
  <CompareProvider>{children}</CompareProvider>
);

describe("CompareContext", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });
    expect(result.current.items).toHaveLength(0);
    expect(result.current.isFull).toBe(false);
  });

  it("toggling a product adds and then removes it", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });
    const product = makeProduct();

    act(() => result.current.toggle(product));
    expect(result.current.items).toHaveLength(1);
    expect(result.current.isSelected(product)).toBe(true);

    act(() => result.current.toggle(product));
    expect(result.current.items).toHaveLength(0);
    expect(result.current.isSelected(product)).toBe(false);
  });

  it("treats the same platform+link pair as the same product", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });
    const product = makeProduct();
    const sameProductDifferentTitle = makeProduct({ title: "Different title text" });

    act(() => result.current.toggle(product));
    act(() => result.current.toggle(sameProductDifferentTitle));

    expect(result.current.items).toHaveLength(0);
  });

  it("does not allow selecting more than MAX_COMPARE_ITEMS", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });

    act(() => {
      for (let i = 0; i < MAX_COMPARE_ITEMS + 2; i++) {
        result.current.toggle(makeProduct({ link: `https://example.com/${i}` }));
      }
    });

    expect(result.current.items).toHaveLength(MAX_COMPARE_ITEMS);
    expect(result.current.isFull).toBe(true);
  });

  it("clear empties the selection and closes the dialog", () => {
    const { result } = renderHook(() => useCompare(), { wrapper });
    act(() => result.current.toggle(makeProduct()));
    act(() => result.current.open());
    expect(result.current.isOpen).toBe(true);

    act(() => result.current.clear());
    expect(result.current.items).toHaveLength(0);
    expect(result.current.isOpen).toBe(false);
  });
});
