import { API_URL, ApiError, apiFetch } from "./client";

export type Msg = {
  id: string;
  kind: "user" | "system";
  author: null | { id: string; role: "buyer" | "seller"; display_name: string };
  body: string;
  attachments: { id: string; name: string; mime: string; size: number }[];
  created_at: string;
  edited: boolean;
  deleted_at: string | null;
  warning?: string;
};

export const getChat = (oid: string) => apiFetch<{ locked: boolean; results: Msg[] }>(`/orders/${oid}/chat`);
export const sendMessage = (oid: string, body: string, attachments: string[] = []) =>
  apiFetch<Msg>(`/orders/${oid}/chat`, { method: "POST", body: { body, attachments } });
export const fileUrl = (id: string) => `${API_URL}/api/v1/files/${id}`;

export async function uploadFile(file: File): Promise<{ id: string; name: string }> {
  const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1];
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_URL}/api/v1/files`, {
    method: "POST", body: fd, credentials: "include", headers: csrf ? { "X-CSRFToken": decodeURIComponent(csrf) } : {},
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data?.error?.code ?? "http_error", data?.error?.message ?? "Ошибка загрузки", data?.error?.details ?? {});
  return data;
}

export const unreadCount = () => apiFetch<{ unread: number }>("/me/notifications/unread-count");
export const readAll = () => apiFetch<{ marked: number }>("/me/notifications/read-all", { method: "POST" });
