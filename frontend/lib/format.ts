/** Money is stored in minor units (kopecks) — D-005. */
export function formatMoney(amountMinor: number, currency = "RUB"): string {
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency, maximumFractionDigits: 2 }).format(
    amountMinor / 100,
  );
}

export function formatCount(n: number): string {
  return new Intl.NumberFormat("ru-RU", { notation: n >= 10_000 ? "compact" : "standard" }).format(n);
}

export function formatDateTime(iso: string, timeZone = "Europe/Moscow"): string {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(iso));
}
