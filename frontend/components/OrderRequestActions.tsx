"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { getTicket, ticketAction, type TicketDetail } from "@/lib/api/support";
import { fieldErrors } from "@/lib/forms";

export function OrderRequestActions({ orderId, requestId }: { orderId: string; requestId: string }) {
  const router = useRouter();
  const toast = useToast();
  const [request, setRequest] = useState<TicketDetail>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let current = true;
    void getTicket(true, requestId).then((ticket) => {
      if (!current) return;
      if (ticket.order === orderId) setRequest(ticket);
      else setError("Обращение относится к другому заказу.");
    }).catch((ex) => {
      if (current) setError(fieldErrors(ex).form ?? "Не удалось открыть обращение.");
    });
    return () => { current = false; };
  }, [orderId, requestId]);

  async function act(action: string, success: string) {
    setBusy(true);
    setError("");
    try {
      const result = await ticketAction(true, requestId, action, undefined, orderId);
      if (action === "assign") setRequest(result);
      else router.push("/staff/tickets");
      toast(success, "success");
    } catch (ex) {
      setError(fieldErrors(ex).form ?? "Не удалось выполнить действие.");
    } finally { setBusy(false); }
  }

  return <div className="grid shrink-0 gap-2 border-b border-border px-4 py-3">
    <Link className="text-sm font-semibold text-accent" href={"/staff/tickets/" + requestId}>К обращению</Link>
    {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    {request && <p className="text-sm font-medium">{request.reason ?? request.subject}</p>}
    {request?.status !== "closed" && request?.assigned_to_me && <div className="flex flex-wrap gap-2">
      <Button type="button" variant="secondary" disabled={busy} onClick={() => void act("refer", "Передано арбитражу")}>Передать арбитражу</Button>
      <Button type="button" variant="ghost" disabled={busy} onClick={() => void act("close", "Запрос закрыт")}>Закрыть запрос</Button>
    </div>}
    {request?.available && <Button type="button" className="w-fit" loading={busy}
      onClick={() => void act("assign", "Обращение взято в работу")}>Взять в работу</Button>}
  </div>;
}
