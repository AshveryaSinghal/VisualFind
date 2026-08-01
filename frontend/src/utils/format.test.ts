import { describe, expect, it } from "vitest";
import {
  formatPrice,
  formatSavings,
  formatDurationMs,
  formatCompactNumber,
  titleCase,
} from "@/utils/format";

describe("formatPrice", () => {
  it("returns an em dash for missing prices", () => {
    expect(formatPrice(null, "INR")).toBe("—");
    expect(formatPrice(undefined, "INR")).toBe("—");
    expect(formatPrice("", "INR")).toBe("—");
  });

  it("formats known currency symbols", () => {
    expect(formatPrice("1999", "INR")).toBe("₹1,999");
    expect(formatPrice(49.99, "USD")).toBe("$49.99");
  });

  it("falls back to the currency code for unknown currencies", () => {
    expect(formatPrice("100", "AED")).toBe("AED 100");
  });

  it("shows the raw number when currency is null", () => {
    expect(formatPrice("500", null)).toBe("500");
  });
});

describe("formatSavings", () => {
  it("returns null when there is nothing to save", () => {
    expect(formatSavings(null, "INR")).toBeNull();
    expect(formatSavings(0, "INR")).toBeNull();
    expect(formatSavings(-10, "INR")).toBeNull();
  });

  it("formats a positive savings amount", () => {
    expect(formatSavings(120, "INR")).toBe("Save ₹120");
  });
});

describe("formatDurationMs", () => {
  it("returns an em dash for missing durations", () => {
    expect(formatDurationMs(null)).toBe("—");
    expect(formatDurationMs(undefined)).toBe("—");
  });

  it("shows milliseconds under a second", () => {
    expect(formatDurationMs(450)).toBe("450ms");
  });

  it("shows seconds with two decimals at or above a second", () => {
    expect(formatDurationMs(2500)).toBe("2.50s");
  });
});

describe("formatCompactNumber", () => {
  it("returns an em dash for missing values", () => {
    expect(formatCompactNumber(null)).toBe("—");
    expect(formatCompactNumber(undefined)).toBe("—");
  });

  it("compacts large numbers", () => {
    expect(formatCompactNumber(1500)).toMatch(/1\.5K/i);
  });
});

describe("titleCase", () => {
  it("capitalizes each word", () => {
    expect(titleCase("google shopping")).toBe("Google Shopping");
  });

  it("ignores extra whitespace", () => {
    expect(titleCase("hello   world")).toBe("Hello World");
  });
});
