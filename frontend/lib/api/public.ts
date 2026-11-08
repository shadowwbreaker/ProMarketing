import { apiFetch } from "./client";
import type { Page } from "./auth";
import type { TrustStatus } from "./social";

export type SellerBrief = {
  id: string; display_name: string; rating: number | null; reviews_count: number; avatar_url?: string | null;
  online?: boolean; member_since?: string;
};

export type OfferCard = {
  id: string;
  title: string;
  platform: "tiktok" | "instagram" | "youtube";
  handle: string;
  profile_url: string;
  category: string;
  language: string;
  geo: string;
  followers: number | null;
  avg_views: number | null;
  videos_in_sample: number;
  stats_updated_at: string | null;
  trust_status: TrustStatus;
  ownership_verified: boolean;
  min_price_minor: number | null;
  currency: string;
  formats: string[];
  seller: SellerBrief;
  description?: string;
  derived_metrics_note?: string;
  offers?: { id: string; ad_format: string; ad_format_label: string; price_minor: number; conditions: string; placement_days: number; publish_within_days: number }[];
};

export type NetworkCard = {
  id: string;
  title: string;
  description: string;
  conditions: string;
  allow_partial_purchase: boolean;
  platforms: string[];
  stats: { accounts: number; total_followers: number; total_avg_views: number; verified_accounts: number; price_minor: number; items_price_minor: number };
  seller: SellerBrief;
  items?: { id: string; price_minor: number; offer: string; account: OfferCard }[];
};

export type Home = {
  popular: OfferCard[];
  new: OfferCard[];
  recommended: OfferCard[];
  networks: NetworkCard[];
  categories: { category: string; count: number }[];
  platforms: string[];
};

export type SellerPage = SellerBrief & {
  bio: string;
  member_since: string;
  last_seen_at: string | null;
  selling_since: string | null;
  completed_orders: number;
  online: boolean;
  is_seller: boolean;
  rating_distribution: Record<"5" | "4" | "3" | "2" | "1", number>;
  accounts: OfferCard[];
  networks: NetworkCard[];
  reviews: { id: string; rating: number; text: string; seller_reply: string; author: string; created_at: string }[];
};

export const getHome = () => apiFetch<Home>("/catalog/home");
export const searchCatalog = (qs: string) => apiFetch<Page<OfferCard>>(`/catalog/accounts${qs ? `?${qs}` : ""}`);
export const getOfferCard = (id: string) => apiFetch<OfferCard>(`/catalog/accounts/${id}`);
export const listCatalogNetworks = (qs = "") => apiFetch<Page<NetworkCard>>(`/catalog/networks${qs ? `?${qs}` : ""}`);
export const getNetworkCard = (id: string) => apiFetch<NetworkCard>(`/catalog/networks/${id}`);
export const getSeller = (id: string) => apiFetch<SellerPage>(`/sellers/${id}`);
export const getCatalogCounts = () => apiFetch<{ accounts: number; tiktok: number; youtube: number; networks: number }>("/catalog/counts");
