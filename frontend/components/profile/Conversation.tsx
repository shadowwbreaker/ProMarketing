"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { DirectMessage, getDirect, sendDirect } from "@/lib/api/direct";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

function shortDate(iso: string) {
  const d = new Date(iso);
  const today = new Date();
  return d.toDateString() === today.toDateString()
    ? d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

/** One pre-order conversation, FunPay-style: author + date per message, input at the bottom. */
export function Conversation({ userId, otherName, empty, onSent }: {
  userId: string;
  otherName: string;
  empty?: ReactNode;
  onSent?: () => void;
}) {
  const { me } = useAuth();
  const [msgs, setMsgs] = useState<DirectMessage[]>([]);
  const [text, setText] = useState("");
  const [warning, setWarning] = useState("");
  const [err, setErr] = useState<string>();
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    getDirect(userId).then((r) => setMsgs(r.results)).catch(() => {});
  }, [userId]);

  useEffect(() => {
    setMsgs([]);
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    box.current?.scrollTo({ top: box.current.scrollHeight });
  }, [msgs]);

  async function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setErr(undefined);
    try {
      const m = await sendDirect(userId, text.trim());
      setMsgs((x) => [...x, m]);
      setWarning(m.warning ?? "");
      setText("");
      onSent?.();
    } catch (ex) {
      setErr(fieldErrors(ex).form);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={box} className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto overscroll-contain px-4 py-4" aria-live="polite">
        {msgs.length === 0
          ? <div className="m-auto text-center">{empty}</div>
          : msgs.map((m) => (
            <div key={m.id} className={`page-enter max-w-[88%] rounded-2xl px-3.5 py-2.5 ${m.mine ? "self-end rounded-br-md bg-accent/[0.08]" : "self-start rounded-bl-md bg-bg"}`}>
              <p className="flex items-baseline justify-between gap-4 text-xs">
                <b className="text-sm">{m.mine ? me?.profile.display_name ?? "Вы" : otherName}</b>
                <span className="shrink-0 text-muted">{shortDate(m.created_at)}</span>
              </p>
              <p className="mt-0.5 whitespace-pre-wrap break-words text-sm">{m.body}</p>
            </div>
          ))}
      </div>
      {warning && <p className="px-5 pb-2 text-xs text-warn">{warning}</p>}
      {err && <p className="px-5 pb-2 text-xs text-danger">{err}</p>}
      <form onSubmit={send} className="flex items-center gap-2 border-t border-border px-4 py-3">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={2000}
          placeholder="Написать…"
          aria-label={`Сообщение для ${otherName}`}
          className="min-w-0 flex-1 bg-transparent px-1 py-2 text-sm outline-none"
        />
        <button type="submit" disabled={busy || !text.trim()} aria-label="Отправить"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-bg text-accent transition-opacity disabled:opacity-40">
          <svg aria-hidden width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
        </button>
      </form>
    </div>
  );
}
