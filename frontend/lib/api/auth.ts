import { apiFetch } from "./client";

export type Me = {
  id: string;
  email: string;
  is_email_verified: boolean;
  status: "active" | "limited" | "blocked";
  date_joined: string;
  profile: { display_name: string; bio: string; country: string; language: string; timezone: string };
  roles: string[];
  permissions: string[];
};

export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const ensureCsrf = () => apiFetch<{ ok: boolean }>("/auth/csrf");
export const getMe = () => apiFetch<Me>("/me");
export const getSession = () => apiFetch<{ user: Me | null }>("/auth/session");
export const login = (email: string, password: string) =>
  apiFetch<Me>("/auth/login", { method: "POST", body: { email, password } });
export const register = (data: { email: string; password: string; display_name: string; as_seller: boolean; accept_terms: boolean }) =>
  apiFetch<Me>("/auth/register", { method: "POST", body: data });
export const logout = () => apiFetch<void>("/auth/logout", { method: "POST" });
export const verifyEmail = (token: string) => apiFetch<{ ok: boolean }>("/auth/verify-email", { method: "POST", body: { token } });
export const resendVerification = () => apiFetch<{ ok: boolean }>("/auth/resend-verification", { method: "POST" });
export const requestPasswordReset = (email: string) =>
  apiFetch<{ ok: boolean }>("/auth/password-reset", { method: "POST", body: { email } });
export const confirmPasswordReset = (token: string, new_password: string) =>
  apiFetch<{ ok: boolean }>("/auth/password-reset/confirm", { method: "POST", body: { token, new_password } });
export const updateProfile = (profile: Partial<Me["profile"]>) => apiFetch<Me>("/me", { method: "PATCH", body: { profile } });
export const becomeSeller = () => apiFetch<Me>("/me/become-seller", { method: "POST" });
export const listMine = <T,>(path: string) => apiFetch<Page<T>>(`/me/${path}`);
