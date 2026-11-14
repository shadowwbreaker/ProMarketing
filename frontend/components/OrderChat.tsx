"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { OrderTermsDetails } from "@/components/OrderTermsDetails";
import { useToast } from "@/components/ui/Toast";
import { fileUrl, getChat, Msg, refreshInbox, sendMessage, uploadFile } from "@/lib/api/chat";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";

export function OrderChat({ orderId, role, onRead }: { orderId: string; role: string; onRead?: () => void }) {
  const toast = useToast();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [locked, setLocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState<string>();
  const [loaded, setLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(true);

  const load = useCallback(async () => {
    if (document.visibilityState === "hidden") return;
    try {
      const c = await getChat(orderId, role !== "staff");
      setMsgs(c.results);
      setLocked(c.locked);
      setError(undefined);
      if (c.marked_read) {
        refreshInbox();
        onRead?.();
      }
    } catch (e) {
      setError(fieldErrors(e).form ?? "Не удалось загрузить чат");
    } finally {
      setLoaded(true);
    }
  }, [orderId, role, onRead]);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 5000); // polls our backend only
    document.addEventListener("visibilitychange", load);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", load); };
  }, [load]);
  useEffect(() => {
    const log = logRef.current;
    if (log && followRef.current) log.scrollTop = log.scrollHeight;
  }, [msgs.length]);

  async function send(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const body = String(new FormData(form).get("body") ?? "");
    setBusy(true);
    try {
      const m = await sendMessage(orderId, body, files.map((f) => f.id));
      if (m.warning) toast(m.warning, "error");
      form.reset();
      setFiles([]);
      followRef.current = true;
      await load();
    } catch (ex) {
      toast(fieldErrors(ex).form ?? "Не отправлено", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {locked && <p className="border-b border-border bg-warn/10 px-4 py-2 text-xs text-warn">По заказу открыта жалоба — переписка зафиксирована и доступна администрации.</p>}
      <div ref={logRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain px-4 py-4 text-sm sm:px-5"
        role="log" aria-label="Чат заказа" onScroll={(e) => {
          const log = e.currentTarget;
          followRef.current = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
        }}>
        {!loaded && <p className="text-sm text-muted">Загружаем переписку…</p>}
        {loaded && !msgs.length && !error && <p className="text-sm text-muted">Сообщений пока нет</p>}
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        {msgs.map((m) =>
          m.kind === "system" ? (
            <article key={m.id}>
              <p className="mb-1 flex flex-wrap justify-between gap-1 text-xs">
                <span><b>ProMarketing</b><span className="ml-2 rounded bg-accent/10 px-1.5 py-0.5 text-accent">Уведомление</span></span>
                <time dateTime={m.created_at} className="text-muted">{formatDateTime(m.created_at)}</time>
              </p>
              <p className="rounded-lg bg-accent/8 px-3 py-2 text-sm">{m.body}</p>
            </article>
          ) : (
            <article key={m.id} className="min-w-0">
              <p className="mb-1 flex flex-wrap justify-between gap-1 text-xs">
                <span className="break-all"><b>{m.author?.display_name}</b>{m.order_brief && <span className="ml-2 rounded bg-bg px-1.5 py-0.5 text-muted">Автоматически</span>}</span>
                <time dateTime={m.created_at} className="text-muted">{formatDateTime(m.created_at)}{m.edited && " · изменено"}</time>
              </p>
              {m.order_brief ? <div className="rounded-lg border border-border p-3 sm:p-4">
                <p className="mb-3 font-semibold">{m.body}</p><OrderTermsDetails terms={m.order_brief} />
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
          <textarea name="body" rows={2} maxLength={5000} aria-label="Сообщение" placeholder="Написать…" className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-base" />
          <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
            <label className="relative inline-flex min-h-10 cursor-pointer items-center rounded-lg px-2 text-sm font-medium text-accent focus-within:ring-2 focus-within:ring-accent">
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
            </label>
            <Button type="submit" loading={busy} disabled={uploading}>Отправить</Button>
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
