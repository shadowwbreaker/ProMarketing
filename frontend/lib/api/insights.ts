import { apiFetch } from "./client";
import type { NetworkCard, OfferCard } from "./public";

export const toggleFavorite = (body: { account?: string; network?: string }) =>
  apiFetch<{ favorite: boolean }>("/me/favorites", { method: "POST", body });
export const getFavorites = () => apiFetch<{ accounts: OfferCard[]; networks: NetworkCard[] }>("/me/favorites");
export const markViewed = (account: string) => apiFetch("/me/viewed", { method: "POST", body: { account } });
export const getViewed = () => apiFetch<OfferCard[]>("/me/viewed");
export const getRecommendations = () => apiFetch<OfferCard[]>("/me/recommendations");
export const compare = (ids: string[]) => apiFetch<OfferCard[]>(`/catalog/compare?ids=${ids.join(",")}`);
export const getReferrals = () => apiFetch<{ code: string; invited: number; invited_with_completed_deals: number; reward_policy: string }>("/me/referrals");
export type Analytics = {
  buyer: { orders_paid: number; spent_minor: number; refunded_minor: number; net_spent_minor: number; avg_item_price_minor: number; views_30d_total: number; cost_per_1000_views_minor: number | null };
  seller?: { items_total: number; items_completed: number; completion_rate_pct: number | null; revenue_minor: number; disputes: number; avg_accept_hours: number | null; by_account: { social_account__title: string; n: number; revenue: number }[] };
};
export const getAnalytics = () => apiFetch<Analytics>("/me/analytics");
export type Report = { expected_avg_views: number | null; checkpoints: { checkpoint: string; status: string; views: number | null; vs_expected_pct: number | null }[] };
export const getReport = (oid: string, iid: string) => apiFetch<Report>(`/orders/${oid}/items/${iid}/report`);

const KEY = "pm.compare";
export function getCompareList(): string[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}
export function setCompareList(ids: string[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(ids.slice(-4)));
  } catch {
    /* storage unavailable — comparison simply isn't remembered */
  }
}
