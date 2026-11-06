import { apiFetch } from "./client";

export type Offer = {
  id: string;
  social_account: string;
  ad_format: string;
  ad_format_label: string;
  title: string;
  price_minor: number;
  currency: string;
  conditions: string;
  placement_days: number;
  publish_within_days: number;
  is_active: boolean;
};

export type Network = {
  id: string;
  title: string;
  description: string;
  total_price_minor: number | null;
  currency: string;
  conditions: string;
  allow_partial_purchase: boolean;
  is_active: boolean;
  items: { id: string; social_account: string; offer: string; price_minor: number; account: { id: string; platform: string; handle: string; title: string } }[];
  stats: { accounts: number; total_followers: number; total_avg_views: number; accounts_with_avg: number; verified_accounts: number; items_price_minor: number; price_minor: number };
};

export const getAdFormats = () => apiFetch<{ value: string; label: string }[]>("/ad-formats");
export const listOffers = (accountId: string) => apiFetch<Offer[]>(`/social-accounts/${accountId}/offers`);
export const createOffer = (accountId: string, body: Partial<Offer>) =>
  apiFetch<Offer>(`/social-accounts/${accountId}/offers`, { method: "POST", body });
export const updateOffer = (id: string, body: Partial<Offer>) => apiFetch<Offer>(`/offers/${id}`, { method: "PATCH", body });
export const setListing = (accountId: string, listed: boolean) =>
  apiFetch(`/social-accounts/${accountId}/listing`, { method: "POST", body: { listed } });
export const removeAccount = (accountId: string) => apiFetch<void>(`/social-accounts/${accountId}/manage`, { method: "DELETE" });
export const listNetworks = () => apiFetch<Network[]>("/networks");
export const getNetwork = (id: string) => apiFetch<Network>(`/networks/${id}`);
export const createNetwork = (body: Partial<Network>) => apiFetch<Network>("/networks", { method: "POST", body });
export const updateNetwork = (id: string, body: Partial<Network>) => apiFetch<Network>(`/networks/${id}`, { method: "PATCH", body });
export const addNetworkItem = (id: string, offer: string) => apiFetch<Network>(`/networks/${id}/items`, { method: "POST", body: { offer } });
export const removeNetworkItem = (id: string, itemId: string) => apiFetch<void>(`/networks/${id}/items/${itemId}`, { method: "DELETE" });

/** Rubles input -> kopecks (D-005). */
export const rublesToMinor = (v: string) => Math.round(parseFloat(v.replace(",", ".")) * 100);
