"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { fileUrl, getChat, Msg, sendMessage, uploadFile } from "@/lib/api/chat";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";

export function OrderChat({ orderId, role }: { orderId: string; role: string }) {
  const toast = useToast();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [locked, setLocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<{ id: string; name: string }[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const c = await getChat(orderId);
      setMsgs(c.results);
      setLocked(c.locked);
    } catch {
      /* chat is optional on the page */
    }
  }, [orderId]);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 5000); // polls our backend only
    return () => clearInterval(t);
  }, [load]);
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "nearest" });
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
      await load();
    } catch (ex) {
      toast(fieldErrors(ex).form ?? "Не отправлено", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="mb-2 font-bold">Чат заказа</h2>
      {locked && <p className="mb-2 text-xs text-warn">По заказу открыта жалоба — переписка зафиксирована и доступна администрации.</p>}
      <div className="mb-3 flex max-h-96 flex-col gap-2 overflow-y-auto text-sm" aria-live="polite">
        {msgs.map((m) =>
          m.kind === "system" ? (
            <p key={m.id} className="text-center text-xs text-muted">{m.body} · {formatDateTime(m.created_at)}</p>
          ) : (
            <div key={m.id} className={`max-w-[85%] rounded-lg px-3 py-2 ${m.author?.role === role ? "self-end bg-accent/10" : "self-start bg-bg"}`}>
              <p className="text-[11px] text-muted">{m.author?.display_name} · {formatDateTime(m.created_at)}{m.edited && " · изменено"}</p>
              {m.deleted_at ? <p className="italic text-muted">Сообщение удалено</p> : <p className="whitespace-pre-line break-words">{m.body}</p>}
              {m.attachments.map((a) => (
                <a key={a.id} href={fileUrl(a.id)} target="_blank" rel="noopener noreferrer" className="block text-xs text-accent">📎 {a.name}</a>
              ))}
            </div>
          ),
        )}
        <div ref={endRef} />
      </div>
      {role !== "staff" && (
        <form onSubmit={send} className="flex flex-col gap-2">
          <textarea name="body" rows={2} aria-label="Сообщение" placeholder="Сообщение продавцу/покупателю" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="cursor-pointer text-xs text-accent">
              Прикрепить скриншот или PDF
              <input type="file" accept="image/*,application/pdf,video/mp4" className="hidden" onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                try {
                  setFiles([...files, await uploadFile(f)]);
                } catch (ex) {
                  toast(fieldErrors(ex).form ?? "Ошибка загрузки", "error");
                }
              }} />
            </label>
            <span className="text-xs text-muted">{files.map((f) => f.name).join(", ")}</span>
            <Button type="submit" loading={busy}>Отправить</Button>
          </div>
          <p className="text-[11px] text-muted">Не переходите к оплате или общению вне платформы — так вы теряете защиту сделки.</p>
        </form>
      )}
    </Card>
  );
}
