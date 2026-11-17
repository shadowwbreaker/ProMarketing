"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useCallback, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import type { Page } from "@/lib/api/auth";
import { complaintUrl, getTicket, listTickets, Ticket, TicketDetail, ticketAction } from "@/lib/api/support";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";
import { useLivePolling } from "@/lib/useLivePolling";

const link = "font-semibold text-accent hover:underline";
const groups = {
  refund: "Возврат средств",
  complaint: "Жалоба на продавца или покупателя",
  other: "Прочее",
};
const control = "rounded-lg border border-border bg-surface px-3 py-2 text-sm";

export function SupportAccess({ staff = false, children }: { staff?: boolean; children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <LoadingState />;
  if (!me) return <Link className={link} href={staff ? "/support/login" : "/login"}>Войти, чтобы открыть обращения</Link>;
  if (staff && !me.permissions.includes("support.work")) return <p role="alert">Доступ только для сотрудников поддержки.</p>;
  return children;
}

export function TicketList({ staff = false }: { staff?: boolean }) {
  const [scope, setScope] = useState("queue");
  const [group, setGroup] = useState("");
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<Page<Ticket>>();
  const [error, setError] = useState("");
  function ticketUrl(ticket: Ticket) {
    if (!staff && ticket.kind === "dispute" && ticket.order) {
      return complaintUrl(ticket.order, ticket.id);
    }
    return (staff ? "/staff/tickets/" : "/support/tickets/") + ticket.id;
  }
  const load = useCallback(async () => {
    try {
      setRows(await listTickets(staff, new URLSearchParams({ scope, group, page: String(page) })));
      setError("");
    } catch (ex) { setError(fieldErrors(ex).form ?? "Не удалось открыть список."); }
  }, [staff, scope, group, page]);
  useLivePolling(load, 10000);

  return <section className={staff ? "flex flex-col gap-4" : "mx-auto flex max-w-3xl flex-col gap-4"}>
    {staff && <div className="flex flex-wrap items-center justify-end gap-4 text-sm">
      <Link className={link} href="/account?tab=profile">Профиль</Link>
    </div>}
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-bold">{staff ? "Техническая поддержка" : "Обращения в поддержку"}</h1>
      {staff ? <Link className={link} href="/staff/orders/search">Найти заказ</Link> : <Link className={link} href="/support">Создать обращение</Link>}
    </div>
    {staff && <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex gap-2" aria-label="Очереди обращений">
        {[["queue", "Запросы"], ["mine", "Мои запросы"]].map(([code, title]) => (
          <Button type="button" key={code} aria-pressed={scope === code} variant={scope === code ? "primary" : "secondary"}
            onClick={() => { if (scope !== code) { setRows(undefined); setScope(code); setPage(1); } }}>{title}</Button>
        ))}
      </div>
      <label className="flex w-full min-w-0 items-center gap-2 text-sm sm:w-auto">Категория
        <select className={control + " min-w-0 flex-1 sm:flex-none"} value={group} onChange={(e) => { setRows(undefined); setGroup(e.target.value); setPage(1); }}>
          <option value="">Все категории</option>
          {Object.entries(groups).map(([code, title]) => <option key={code} value={code}>{title}</option>)}
        </select>
      </label>
    </div>}
    {error && <ErrorState message={error} onRetry={() => void load()} />}
    {!rows && !error && <LoadingState />}
    {rows && (rows.results.length ? <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
      {rows.results.map((t) => <li key={t.kind + t.id}>
        <Link className="flex flex-wrap items-start justify-between gap-2 px-4 py-4 hover:bg-bg" href={ticketUrl(t)}>
          <div className="min-w-0">
            <p className="break-words font-semibold">{t.reason ?? t.subject}</p>
            {t.kind === "ticket" && t.reason !== t.subject && <p className="mt-1 text-sm">{t.subject}</p>}
            {(t.author || t.order_number) && <p className="mt-1 break-words text-sm text-muted">
              {[staff && t.group ? groups[t.group as keyof typeof groups] : undefined, t.author, t.order_number ? "заказ #" + t.order_number : undefined]
                .filter(Boolean).join(" · ")}
            </p>}
          </div>
          <div className="text-sm text-muted sm:text-right">
            <p>{t.status_label}</p>
            <time dateTime={t.created_at}>{formatDateTime(t.created_at)}</time>
          </div>
        </Link>
      </li>)}
    </ul> : <EmptyState title={staff && scope === "queue" ? "Новых запросов нет" : "Обращений пока нет"} />)}
    {rows && (rows.previous || rows.next) && <div className="flex items-center justify-between">
      <Button type="button" variant="secondary" disabled={!rows.previous} onClick={() => { setRows(undefined); setPage(page - 1); }}>Назад</Button>
      <span className="text-sm text-muted">Страница {page}</span>
      <Button type="button" variant="secondary" disabled={!rows.next} onClick={() => { setRows(undefined); setPage(page + 1); }}>Дальше</Button>
    </div>}
  </section>;
}

export function TicketThread({ id, staff = false }: { id: string; staff?: boolean }) {
  const [ticket, setTicket] = useState<TicketDetail>();
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setTicket(await getTicket(staff, id)); setError(""); }
    catch (ex) { setTicket(undefined); setError(fieldErrors(ex).form ?? "Не удалось открыть обращение."); }
  }, [id, staff]);
  useLivePolling(load, 5000);

  async function act(action: string, reply?: string) {
    setBusy(true);
    setActionError("");
    try { setTicket(await ticketAction(staff, id, action, reply)); return true; }
    catch (ex) { setActionError(fieldErrors(ex).form ?? "Действие не выполнено."); return false; }
    finally { setBusy(false); }
  }

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (await act("reply", String(new FormData(form).get("body")))) form.reset();
  }

  return <section className="mx-auto flex w-full max-w-3xl flex-col gap-4">
    <Link className={link} href={staff ? "/staff/tickets" : "/support/tickets"}>{staff ? "К запросам" : "Мои обращения"}</Link>
    {error && <ErrorState message={error} onRetry={() => void load()} />}
    {!ticket && !error && <LoadingState />}
    {ticket && <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-bold">{ticket.subject}</h1>
          <p className="mt-1 text-sm text-muted">{ticket.status_label}{ticket.author && " · " + ticket.author}</p>
        </div>
        {ticket.order && <Link className={link}
          href={staff ? "/orders/" + ticket.order + "?request=" + ticket.id + "#chat" :
            ticket.arbitration_id ? complaintUrl(ticket.order, ticket.arbitration_id) : "/orders/" + ticket.order}>
          Открыть заказ #{ticket.order_number}
        </Link>}
      </div>
      {actionError && <p role="alert" className="text-sm text-danger">{actionError}</p>}
      <Card>
        <ol aria-label="Переписка обращения" className="flex flex-col gap-3">
          {ticket.messages.map((m) => <li key={m.id} className={"rounded-lg px-3 py-2 " + (m.is_staff_reply ? "bg-accent/10" : "bg-bg")}>
            <div className="flex flex-wrap justify-between gap-1 text-xs text-muted">
              <strong>{m.is_staff_reply ? "Техническая поддержка" : "Пользователь"}</strong>
              <time dateTime={m.created_at}>{formatDateTime(m.created_at)}</time>
            </div>
            <p className="mt-1 whitespace-pre-wrap break-words text-sm">{m.body}</p>
          </li>)}
        </ol>
        {ticket.available && staff && <Button type="button" className="mt-4" loading={busy} onClick={() => void act("assign")}>Взять в работу</Button>}
        {ticket.status !== "closed" && ticket.status !== "arbitration" && (!staff || ticket.assigned_to_me) && <form method="post" onSubmit={send} className="mt-4 grid gap-3">
          <label className="grid gap-1 text-sm">Сообщение
            <textarea className={control} name="body" rows={3} required maxLength={10000} />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" loading={busy}>Отправить</Button>
            {staff && !ticket.order && <Button type="button" variant="secondary" disabled={busy} onClick={() => void act("close")}>Закрыть запрос</Button>}
          </div>
        </form>}
      </Card>
    </>}
  </section>;
}
