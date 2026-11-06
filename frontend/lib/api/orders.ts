import { apiFetch } from "./client";

export type Item = {
  id: string;
  status: string;
  price_minor: number;
  fee_minor: number;
  seller_amount_minor: number;
  accept_deadline: string | null;
  publish_deadline: string | null;
  placement_until: string | null;
  accepted_at: string | null;
  published_at: string | null;
  confirm_deadline: string | null;
  confirmed_at: string | null;
  payout_available_at: string | null;
  account: { id: string; platform: string; handle: string; title: string; profile_url: string; ad_format_label: string };
  proofs: { id: string; video_url: string; published_at: string; notes: string }[];
  payout: null | { id?: string; status: string; amount_minor?: number; available_at: string };
  refunded_minor: number;
  checks: { trigger: string; result: string; checked_at: string }[];
  review: null | { id: string; rating: number; text: string; seller_reply: string; moderation_status: string };
};

export type Order = {
  id: string;
  status: string;
  total_minor: number;
  currency: string;
  fee_bps: number;
  created_at: string;
  paid_at: string | null;
  materials_delivered_at: string | null;
  seller_terms_accepted_at: string | null;
  items: Item[];
  terms: Record<string, unknown> & { version: number; brand: string; brief: string; placement_days: number };
  buyer: { id: string; display_name: string; last_seen_at: string | null };
  seller: { id: string; display_name: string; last_seen_at: string | null };
  role: "buyer" | "seller" | "staff";
  proposals: { id: string; changes: Record<string, string>; comment: string; status: string; proposed_by: string }[];
};

export type OrderEvent = { seq: number; type: string; item: string | null; from: string; to: string; created_at: string };

export const createOrder = (body: Record<string, unknown>) => apiFetch<Order>("/orders", { method: "POST", body });
export const getOrder = (id: string) => apiFetch<Order>(`/orders/${id}`);
export const getOrderEvents = (id: string) => apiFetch<OrderEvent[]>(`/orders/${id}/events`);
export const itemAction = (oid: string, iid: string, action: string, body?: unknown) =>
  apiFetch<Order>(`/orders/${oid}/items/${iid}/${action}`, { method: "POST", body: body ?? {} });
export const orderAction = (oid: string, action: string, body?: unknown) =>
  apiFetch<Order>(`/orders/${oid}/${action}`, { method: "POST", body: body ?? {} });
export const startPayment = (oid: string) =>
  apiFetch<{ payment_id: string; confirmation_url: string; status: string }>(`/orders/${oid}/pay`, { method: "POST" });
export const mockComplete = (paymentId: string, status: "succeeded" | "cancelled") =>
  apiFetch<{ ok: boolean; outcome: string }>(`/payments/mock/${paymentId}/complete`, { method: "POST", body: { status } });
export const decideTerms = (oid: string, pid: string, accept: boolean) =>
  apiFetch<Order>(`/orders/${oid}/terms/${pid}/decide`, { method: "POST", body: { accept } });

export type PayoutRow = { id: string; status: string; amount_minor: number; available_at: string; paid_at: string | null; order: string; account: string };
export const listPayouts = () => apiFetch<PayoutRow[]>("/me/payouts");
export const withdrawPayout = (id: string) => apiFetch<PayoutRow>(`/me/payouts/${id}/withdraw`, { method: "POST" });
export const retryPayout = (id: string) => apiFetch<PayoutRow>(`/me/payouts/${id}/retry`, { method: "POST" });

export const STATUS_LABEL: Record<string, string> = {
  DRAFT: "Черновик", AWAITING_PAYMENT: "Ожидает оплаты", PAID: "Оплачен", AWAITING_SELLER_ACCEPTANCE: "Ждёт принятия продавцом",
  IN_PROGRESS: "В работе", AWAITING_PUBLICATION: "Ждёт публикации", PUBLISHED: "Опубликовано",
  AWAITING_BUYER_CONFIRMATION: "Ждёт подтверждения покупателем", COMPLETED: "Выполнен", DISPUTED: "Спор", CANCELLED: "Отменён",
  REFUND_PENDING: "Возврат в обработке", REFUNDED: "Возвращён", PARTIALLY_REFUNDED: "Частично возвращён", EXPIRED: "Истёк",
};
export const PAYOUT_LABEL: Record<string, string> = {
  hold: "Ожидание 48 ч", suspended: "Приостановлена (жалоба)", available: "Доступна к выводу", requested: "Запрошена",
  pending_reconciliation: "Сверка с провайдером", paid: "Выплачена", failed: "Ошибка выплаты", cancelled: "Отменена (возврат)",
};

export const leaveReview = (oid: string, iid: string, rating: number, text: string) =>
  apiFetch(`/orders/${oid}/items/${iid}/review`, { method: "POST", body: { rating, text } });
export const replyReview = (rid: string, text: string) => apiFetch(`/reviews/${rid}/reply`, { method: "POST", body: { text } });
export const complainReview = (rid: string, reason: string) => apiFetch(`/reviews/${rid}/complain`, { method: "POST", body: { reason } });
