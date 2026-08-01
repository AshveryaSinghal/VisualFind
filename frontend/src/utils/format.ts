
const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: "₹",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

export function formatPrice(
  price: string | number | null | undefined,
  currency: string | null | undefined
): string {
  if (price === null || price === undefined || price === "") return "—";

  const numeric = typeof price === "number" ? price : Number(price);
  const display = Number.isFinite(numeric)
    ? numeric.toLocaleString("en-IN", {
        minimumFractionDigits: numeric % 1 === 0 ? 0 : 2,
        maximumFractionDigits: 2,
      })
    : String(price);

  if (!currency) return display;

  const symbol = CURRENCY_SYMBOLS[currency.toUpperCase()];
  return symbol ? `${symbol}${display}` : `${currency} ${display}`;
}

export function formatSavings(
  savings: number | null | undefined,
  currency: string | null | undefined
): string | null {
  if (savings === null || savings === undefined || savings <= 0) return null;
  return `Save ${formatPrice(savings, currency)}`;
}

export function formatRelativeDate(iso: string | Date): string {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.round(diffMs / 1000);

  const divisions: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["week", 60 * 60 * 24 * 7],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
  ];

  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  if (diffSec < 45) return "just now";

  for (const [unit, secondsInUnit] of divisions) {
    if (Math.abs(diffSec) >= secondsInUnit) {
      return rtf.format(-Math.round(diffSec / secondsInUnit), unit);
    }
  }
  return rtf.format(-diffSec, "second");
}

export function formatDateTime(iso: string | Date): string {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateTimeInZone(iso: string | Date, timeZone?: string | null): string {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  if (!timeZone) return formatDateTime(date);
  try {
    return date.toLocaleString("en-IN", {
      timeZone,
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return formatDateTime(date);
  }
}

export function formatDurationMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return Intl.NumberFormat("en", { notation: "compact" }).format(value);
}

export function titleCase(value: string): string {
  return value
    .split(" ")
    .filter(Boolean)
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

export function recordToNamedCount(record: Record<string, number>): { name: string; count: number }[] {
  return Object.entries(record)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}
