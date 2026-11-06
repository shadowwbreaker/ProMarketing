import { apiFetch } from "./client";

export type Reason = { code: string; title: string; allowed_for: "buyer" | "seller" | "both" };
export type Dispute = {
  id: string;
  order: string;
  status: string;
  priority: string;
  reason: { code: string; title: string };
  description: string;
  opened_by_role: "buyer" | "seller";
  response_due_at: string | null;
  response_overdue: boolean;
  has_counterclaim: boolean;
  created_at: string;
  resolved_at: string | null;
  appeal_of: string | null;
  items: { order_item: string; status_before: string; active: boolean; account: string; price_minor: number }[];
  messages: { id: string; author: string; author_name: string; is_staff: boolean; visibility: string; body: string; created_at: string }[];
  evidence: { id: string; submitted_by: string; url: string; description: string; attachment: string | null; created_at: string }[];
  decisions: { id: string; item: string | null; type: string; comment: string; refund_amount_minor: number | null; created_at: string; actions: { type: string; status: string; error: string }[] }[];
};
export type Evidence = { attachment?: string; url?: string; description?: string };

export const getReasons = () => apiFetch<Reason[]>("/dispute-reasons");
export const orderDisputes = (oid: string) => apiFetch<Dispute[]>(`/orders/${oid}/disputes`);
export const openDispute = (oid: string, body: { reason: string; description: string; items?: string[]; evidence?: Evidence[] }) =>
  apiFetch<Dispute>(`/orders/${oid}/disputes/open`, { method: "POST", body });
export const replyDispute = (id: string, body: string, evidence: Evidence[] = []) =>
  apiFetch<Dispute>(`/disputes/${id}/reply`, { method: "POST", body: { body, evidence } });
export const appealDispute = (id: string, reason: string) => apiFetch<Dispute>(`/disputes/${id}/appeal`, { method: "POST", body: { reason } });

export const DISPUTE_STATUS: Record<string, string> = {
  OPEN: "Открыт", WAITING_SELLER: "Ждём ответа продавца", WAITING_BUYER: "Ждём ответа покупателя", UNDER_REVIEW: "На рассмотрении",
  EVIDENCE_REQUESTED: "Запрошены доказательства", ESCALATED: "Передан старшему администратору", RESOLVED: "Решён",
  REJECTED: "Отклонён", CLOSED: "Закрыт", APPEALED: "Апелляция",
};
export const DECISION_LABEL: Record<string, string> = {
  full_refund: "Полный возврат", partial_refund: "Частичный возврат", reject: "Отказ в жалобе", redo: "Повторное выполнение",
  extend: "Продление срока", in_favor_of_seller: "В пользу продавца", request_evidence: "Запрос доказательств",
  escalate: "Передача старшему", sanction: "Санкции",
};

// staff
export const staffQueue = (qs = "") => apiFetch<{ count: number; results: Record<string, unknown>[] }>(`/staff/disputes${qs ? `?${qs}` : ""}`);
export const staffDispute = (id: string) => apiFetch<Dispute & Record<string, unknown>>(`/staff/disputes/${id}`);
export const staffAction = (id: string, action: string, body: Record<string, unknown> = {}) =>
  apiFetch<Dispute & Record<string, unknown>>(`/staff/disputes/${id}/${action}`, { method: "POST", body });
export const createTicket = (body: { subject: string; body: string; order?: string; category?: string }) =>
  apiFetch<{ id: string }>("/support/tickets", { method: "POST", body });
