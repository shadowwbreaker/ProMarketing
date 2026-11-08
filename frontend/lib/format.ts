/** Money is stored in minor units (kopecks) — D-005. */
export function formatMoney(amountMinor: number, currency = "RUB"): string {
  const whole = amountMinor % 100 === 0; // "9 000 ₽", not "9 000,00 ₽"
  return new Intl.NumberFormat("ru-RU", {
    style: "currency", currency, minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2,
  }).format(amountMinor / 100);
}

export function formatCount(n: number): string {
  return new Intl.NumberFormat("ru-RU", { notation: n >= 10_000 ? "compact" : "standard" }).format(n);
}

export function formatDateTime(iso: string, timeZone = "Europe/Moscow"): string {
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(iso));
}

function plural(n: number, one: string, few: string, many: string): string {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}

/** "3 месяца назад", "сегодня" — for profile pages. */
export function timeAgo(iso: string, now = new Date()): string {
  const days = Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000);
  if (days < 1) return "сегодня";
  if (days < 30) return `${days} ${plural(days, "день", "дня", "дней")} назад`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} ${plural(months, "месяц", "месяца", "месяцев")} назад`;
  const years = Math.floor(days / 365);
  return `${years} ${plural(years, "год", "года", "лет")} назад`;
}

export const reviewsWord = (n: number) => plural(n, "отзыв", "отзыва", "отзывов");
