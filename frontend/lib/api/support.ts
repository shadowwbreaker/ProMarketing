import type { Page } from "./auth";
import type { Evidence } from "./disputes";
import { apiFetch } from "./client";

export type Ticket = {
  id: string; kind: "ticket" | "dispute"; subject: string; category: string; topic: string; reason?: string;
  status: string; status_label: string;
  created_at: string; order: string | null; order_number: string | null; author?: string;
  assigned_to_me?: boolean; available?: boolean; group?: string; arbitration_id?: string;
};
export type TicketDetail = Ticket & { messages: {
  id: string; body: string; is_staff_reply: boolean; created_at: string;
}[] };

export const getTopics = () => apiFetch<Record<string, string>>("/support/topics");
const ticketPath = (staff: boolean) => staff ? "/staff/tickets" : "/support/tickets";
export const listTickets = (staff: boolean, params: URLSearchParams) =>
  apiFetch<Page<Ticket>>(ticketPath(staff) + "?" + params);
export const getTicket = (staff: boolean, id: string) => apiFetch<TicketDetail>(ticketPath(staff) + "/" + id);
export type ComplaintOptions = { reasons: { code: string; title: string }[]; items: { id: string; title: string }[] };
export const getComplaintOptions = (number: string, signal: AbortSignal) =>
  apiFetch<ComplaintOptions>("/support/order-options?" + new URLSearchParams({ number }), { signal });
export const submitTicket = (body: {
  category: string; body: string; order_number: string; reason?: string; items?: string[]; evidence?: Evidence[];
}) => apiFetch<Pick<Ticket, "id" | "kind" | "order">>("/support/tickets", { method: "POST", body });
export const complaintUrl = (order: string, id: string) => "/orders/" + order + "#dispute-" + id;
export const ticketAction = (staff: boolean, id: string, action: string, reply?: string, order?: string) =>
  apiFetch<TicketDetail>(ticketPath(staff) + "/" + id + (staff ? "/" + action : ""),
    { method: "POST", body: { body: reply, order } });
