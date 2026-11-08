import { apiFetch } from "./client";

export type TrustStatus = "VERIFIED" | "MANUAL" | "STALE" | "UNAVAILABLE" | "SUSPICIOUS" | "ERROR";

export type StatsView = {
  trust_status: TrustStatus;
  followers: number | null;
  avg_views: number | null;
  videos_in_sample: number;
  fetched_at: string | null;
  source: string | null;
  derived_metrics_note?: string;
};

export type SocialAccount = {
  id: string;
  platform: "tiktok" | "instagram" | "youtube";
  handle: string;
  profile_url: string;
  title: string;
  category: string;
  language: string;
  geo: string;
  description: string;
  status: string;
  is_listed: boolean;
  ownership_verified: boolean;
  ownership_code?: string;
  ownership_check_supported?: boolean;
  statistics: StatsView;
  refresh?: {
    last_requested_at: string | null;
    next_allowed_at: string | null;
    interval_hours: number;
    last_job: null | { id: string; status: string; error_code: string; error_message: string; finished_at: string | null };
  };
};

export type StatsHistory = {
  results: {
    id: string;
    followers: number;
    avg_views: number | null;
    videos_in_sample: number;
    source: string;
    trust_status: TrustStatus;
    fetched_at: string;
    notes: string;
    videos: { external_video_id: string; url: string; published_at: string | null; views: number; is_short_heuristic: boolean }[];
  }[];
  failed_jobs: { id: string; error_code: string; error_message: string; finished_at: string }[];
};

export const createSocialAccount = (body: Record<string, unknown>) =>
  apiFetch<SocialAccount>("/social-accounts", { method: "POST", body });
export const getSocialAccount = (id: string) => apiFetch<SocialAccount>(`/social-accounts/${id}`);
export const refreshSocialAccount = (id: string) =>
  apiFetch<{ job_id: string; account: SocialAccount }>(`/social-accounts/${id}/refresh`, { method: "POST", body: { consent: true } });
export const getStatsHistory = (id: string) => apiFetch<StatsHistory>(`/social-accounts/${id}/statistics`);
export const saveManualStats = (id: string, followers: number, video_views: number[]) =>
  apiFetch<SocialAccount>(`/social-accounts/${id}/manual-statistics`, { method: "POST", body: { followers, video_views } });
export const startTikTokOAuth = () => apiFetch<{ authorize_url: string }>("/social-accounts/oauth/tiktok/start?consent=1");
export const finishTikTokOAuth = (code: string, state: string) =>
  apiFetch<SocialAccount>("/social-accounts/oauth/tiktok/callback", { method: "POST", body: { code, state } });

export const PLATFORM_LABEL: Record<string, string> = { tiktok: "TikTok", instagram: "Instagram Reels", youtube: "YouTube Shorts" };
export const startOwnership = (id: string) => apiFetch<{ code: string }>(`/social-accounts/${id}/ownership/start`, { method: "POST" });
export const checkOwnership = (id: string) =>
  apiFetch<{ verified: boolean; account: SocialAccount }>(`/social-accounts/${id}/ownership/check`, { method: "POST" });
export const startClaim = (id: string) => apiFetch<{ code: string }>(`/social-accounts/${id}/claim/start`, { method: "POST" });
export const checkClaim = (id: string) =>
  apiFetch<{ claimed: boolean; account: SocialAccount | null }>(`/social-accounts/${id}/claim/check`, { method: "POST" });
