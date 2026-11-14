"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { OrderTermsDetails } from "@/components/OrderTermsDetails";
import { useToast } from "@/components/ui/Toast";
import { ConversationOrder, fileUrl, getChat, getConversation, Msg, refreshInbox, sendMessage, uploadFile } from "@/lib/api/chat";
import { sendDirect } from "@/lib/api/direct";
import { STATUS_LABEL } from "@/lib/api/orders";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";
import { useLivePolling } from "@/lib/useLivePolling";

export function OrderChat({ orderId, role, peerId, empty, onOrders }: {
  orderId?: string; role?: string; peerId?: string; empty?: ReactNode;
  onOrders?: (peerId: string, orders: ConversationOrder[]) => void;
}) {
  const toast = useToast();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [locked, setLocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState<string>();
  const [loaded, setLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [orders, setOrders] = useState<ConversationOrder[]>([]);
  const [selection, setSelection] = useState<string>();
  const [earlier, setEarlier] = useState<Msg[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [olderBusy, setOlderBusy] = useState(false);
  const startedHistory = useRef(false);
  const version = useRef<string>(undefined);
  const logRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(true);
  const destination = selection ?? orderId ?? orders.find((o) =>
    !["COMPLETED", "REFUNDED", "PARTIALLY_REFUNDED", "EXPIRED", "CANCELLED"].includes(o.status),
  )?.id ?? "";

  const load = useCallback(async () => {
    try {
      if (peerId) {
        const c = await getConversation(peerId, { version: version.current });
        setError(undefined);
        if ("unchanged" in c) return;
        version.current = c.version;
        setMsgs((previous) => {
          if (!startedHistory.current || !c.results.length) return c.results;
          const first = c.results[0].created_at;
          return [...previous.filter((message) => message.created_at < first), ...c.results];
        });
        setOrders(c.orders);
        onOrders?.(peerId, c.orders);
        if (!startedHistory.current) setCursor(c.next);
        if (c.marked_read) refreshInbox();
      } else if (orderId) {
        const c = await getChat(orderId, role !== "staff");
        setMsgs(c.results);
        setLocked(c.locked);
        if (c.marked_read) refreshInbox();
      }
      setError(undefined);
    } catch (e) {
      setError(fieldErrors(e).form ?? "Не удалось загрузить чат");
    } finally {
      setLoaded(true);
    }
  }, [orderId, role, peerId, onOrders]);
  useLivePolling(load, peerId ? 2000 : 5000, "conversation-updated");
  useEffect(() => {
    const log = logRef.current;
    if (log && followRef.current) log.scrollTop = log.scrollHeight;
  }, [msgs]);

  async function loadOlder() {
    if (!peerId || !cursor) return;
    setOlderBusy(true);
    try {
      const c = await getConversation(peerId, { before: cursor });
      if ("unchanged" in c) return;
      const log = logRef.current;
      const height = log?.scrollHeight ?? 0;
      const scrollTop = log?.scrollTop ?? 0;
      startedHistory.current = true;
      followRef.current = false;
      setEarlier((previous) => [...c.results, ...previous]);
      setCursor(c.next);
      requestAnimationFrame(() => { if (log) log.scrollTop = scrollTop + log.scrollHeight - height; });
    } catch (ex) {
      toast(fieldErrors(ex).form ?? "Не удалось загрузить историю", "error");
    } finally {
      setOlderBusy(false);
    }
  }

  async function send(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const body = String(new FormData(form).get("body") ?? "");
    setBusy(true);
    try {
      const m = destination
        ? await sendMessage(destination, body, files.map((f) => f.id))
        : await sendDirect(peerId!, body);
      if (m.warning) toast(m.warning, "error");
      form.reset();
      setFiles([]);
      followRef.current = true;
      window.dispatchEvent(new Event("conversation-updated"));
      refreshInbox();
    } catch (ex) {
      toast(fieldErrors(ex).form ?? "Не отправлено", "error");
    } finally {
      setBusy(false);
    }
  }

  const currentIds = new Set(msgs.map((message) => message.id));
  const messages = [...earlier.filter((message) => !currentIds.has(message.id)), ...msgs];
  const showLock = locked || orders.some((order) => order.id === destination && order.locked);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {showLock && <p className="border-b border-border bg-warn/10 px-4 py-2 text-xs text-warn">По заказу открыта жалоба — переписка зафиксирована и доступна администрации.</p>}
      <div ref={logRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-4 py-4 text-sm sm:px-5"
        role="log" aria-label={orderId ? "Чат заказа" : "Переписка"} onScroll={(e) => {
          const log = e.currentTarget;
          followRef.current = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
        }}>
        {!loaded && <p className="text-sm text-muted">Загружаем переписку…</p>}
        {loaded && !messages.length && !error && (empty ?? <p className="text-sm text-muted">Сообщений пока нет</p>)}
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        {cursor && <Button type="button" variant="secondary" loading={olderBusy} onClick={() => void loadOlder()}>Показать предыдущие сообщения</Button>}
        {messages.map((m) =>
          m.kind === "system" ? (
            <article key={m.id}>
              <p className="mb-1 flex flex-wrap justify-between gap-1 text-xs">
                <span><b>ProMarketing</b><span className="ml-2 rounded bg-accent/10 px-1.5 py-0.5 text-accent">Уведомление</span></span>
                <time dateTime={m.created_at} className="text-muted">{formatDateTime(m.created_at)}</time>
              </p>
              <p className="rounded-lg bg-accent/8 px-3 py-2 text-sm">{m.body}
                {m.order_id && <Link href={`/orders/${m.order_id}`} className="ms-2 whitespace-nowrap font-medium text-accent hover:underline">#{m.order_id.slice(0, 8)}</Link>}
              </p>
            </article>
          ) : (
            <article key={m.id} className="min-w-0">
              <p className="mb-1 flex flex-wrap justify-between gap-1 text-xs">
                <span className="break-all"><b>{m.author?.display_name}</b>{m.order_brief && <span className="ml-2 rounded bg-bg px-1.5 py-0.5 text-muted">Автоматически</span>}</span>
                <time dateTime={m.created_at} className="text-muted">{formatDateTime(m.created_at)}{m.edited && " · изменено"}</time>
              </p>
              {m.order_brief ? <div className="rounded-lg border border-border p-3 sm:p-4">
                <p className="mb-3 font-semibold">{m.body}
                  {m.order_id && <Link href={`/orders/${m.order_id}`} className="ms-2 whitespace-nowrap text-accent hover:underline">#{m.order_id.slice(0, 8)}</Link>}
                </p><OrderTermsDetails terms={m.order_brief} />
              </div> : m.deleted_at ? <p className="italic text-muted">Сообщение удалено</p> : <p className="whitespace-pre-wrap break-words">{m.body}</p>}
              {m.attachments.map((a) => (
                <a key={a.id} href={fileUrl(a.id)} target="_blank" rel="noopener noreferrer" className="block text-xs text-accent">📎 {a.name}</a>
              ))}
            </article>
          ),
        )}
      </div>
      {role !== "staff" && (
        <form onSubmit={send} className="shrink-0 border-t border-border p-3 sm:px-4">
          {peerId && orders.length > 0 && <label className="mb-2 flex items-center gap-2 text-xs text-muted">
            К заказу
            <select value={destination} disabled={uploading || busy} onChange={(event) => { setSelection(event.target.value); setFiles([]); }}
              className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-2 py-1.5 text-sm text-text">
              <option value="">Личное сообщение</option>
              {orders.map((order) => <option key={order.id} value={order.id}>#{order.id.slice(0, 8)} · {order.title} · {STATUS_LABEL[order.status] ?? order.status}</option>)}
            </select>
          </label>}
          <textarea name="body" rows={2} maxLength={destination ? 5000 : 2000} aria-label="Сообщение" placeholder="Написать…" className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-base" />
          <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
            {destination && <label className="relative inline-flex min-h-10 cursor-pointer items-center rounded-lg px-2 text-sm font-medium text-accent focus-within:ring-2 focus-within:ring-accent">
              {uploading ? "Загружаем файл…" : "Прикрепить файл"}
              <input type="file" disabled={uploading || busy} accept="image/*,application/pdf,video/mp4" className="absolute inset-0 h-full w-full cursor-pointer opacity-0" aria-label="Прикрепить файл" onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                e.target.value = "";
                setUploading(true);
                try {
                  const uploaded = await uploadFile(f);
                  setFiles((previous) => [...previous, uploaded]);
                } catch (ex) {
                  toast(fieldErrors(ex).form ?? "Ошибка загрузки", "error");
                } finally {
                  setUploading(false);
                }
              }} />
            </label>}
            <Button type="submit" className="ms-auto" loading={busy} disabled={uploading}>Отправить</Button>
          </div>
          {files.length > 0 && <ul className="mt-1 flex flex-wrap gap-2 text-xs">{files.map((file) => (
            <li key={file.id}><button type="button" className="rounded bg-bg px-2 py-1 break-all" onClick={() => setFiles((previous) => previous.filter((f) => f.id !== file.id))}
              aria-label={`Убрать вложение ${file.name}`}>{file.name} ×</button></li>
          ))}</ul>}
        </form>
      )}
    </div>
  );
}
