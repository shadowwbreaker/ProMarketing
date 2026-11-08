import { apiFetch } from "./client";

export type DirectMessage = { id: string; mine: boolean; body: string; created_at: string; warning?: string };
export type DirectThread = {
  user: { id: string; display_name: string };
  last_message: string;
  last_message_at: string;
  unread: number;
};

export const getDirect = (userId: string) => apiFetch<{ results: DirectMessage[] }>(`/direct/${userId}`);
export const sendDirect = (userId: string, body: string) =>
  apiFetch<DirectMessage>(`/direct/${userId}`, { method: "POST", body: { body } });
export const listDirect = () => apiFetch<{ results: DirectThread[] }>("/direct");
