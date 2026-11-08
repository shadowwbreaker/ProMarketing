import { apiFetch } from "./client";

export type DirectMessage = { id: string; mine: boolean; body: string; created_at: string; warning?: string };
export type DirectThread = {
  user: { id: string; display_name: string; avatar_url?: string | null; online: boolean; date_joined: string; blocked: boolean };
  last_message: string;
  last_message_at: string;
  unread: number;
};

export const getDirect = (userId: string) => apiFetch<{ results: DirectMessage[] }>(`/direct/${userId}`);
export const sendDirect = (userId: string, body: string) =>
  apiFetch<DirectMessage>(`/direct/${userId}`, { method: "POST", body: { body } });
export const listDirect = () => apiFetch<{ results: DirectThread[] }>("/direct");
export const directUnread = () => apiFetch<{ unread: number }>("/direct/unread-count");
