"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Avatar } from "@/components/profile/Avatar";
import { DirectMessage, getDirect, sendDirect } from "@/lib/api/direct";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { reviewsWord } from "@/lib/format";

type Props = { userId: string; avatar?: string | null; name: string; online: boolean; rating: number | null; reviews: number };

/** Right-hand panel on a profile: "write to the seller before paying" (FunPay-style). */
export function DirectChat({ userId, avatar, name, online, rating, reviews }: Props) {
  const { me, loading } = useAuth();
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
    if (!me || me.id === userId) return;
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [me, userId, load]);

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
    } catch (ex) {
      setErr(fieldErrors(ex).form);
    } finally {
      setBusy(false);
    }
  }

  const own = me?.id === userId;
  return (
    <aside className="flex h-[32rem] flex-col rounded-xl border border-border bg-surface lg:sticky lg:top-4">
      <div className="flex items-center gap-3 border-b border-border p-4">
        <Avatar id={userId} name={name} size={44} src={avatar} />
        <div className="min-w-0">
          <p className="truncate font-bold">{name}</p>
          <p className={`text-xs font-semibold ${online ? "text-ok" : "text-muted"}`}>{online ? "Онлайн" : "Не в сети"}</p>
        </div>
      </div>
      <div ref={box} className="flex flex-1 flex-col gap-2 overflow-y-auto p-4" aria-live="polite">
        {msgs.length === 0 ? (
          <div className="m-auto text-center">
            <p className="text-2xl tracking-widest text-warn">★★★★★</p>
            <p className="mt-2 text-sm font-semibold">
              {rating != null ? `${rating.toFixed(1)} · ` : ""}{reviews} {reviewsWord(reviews)}
            </p>
            <p className="mt-2 text-sm text-muted">{own ? "Здесь покупатели пишут вам до оплаты" : "Напишите продавцу перед оплатой"}</p>
          </div>
        ) : (
          msgs.map((m) => (
            <p key={m.id} className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-sm ${m.mine ? "self-end bg-accent text-accent-ink" : "self-start bg-bg"}`}>
              {m.body}
            </p>
          ))
        )}
      </div>
      {warning && <p className="px-4 pb-2 text-xs text-warn">{warning}</p>}
      {err && <p className="px-4 pb-2 text-xs text-danger">{err}</p>}
      {loading ? null : !me ? (
        <p className="border-t border-border p-4 text-center text-sm">
          <Link href="/login" className="font-semibold text-accent">Войдите</Link>, чтобы написать продавцу
        </p>
      ) : own ? (
        <p className="border-t border-border p-4 text-center text-sm text-muted">
          Все переписки — в <Link href="/account?tab=messages" className="font-semibold text-accent">Сообщениях</Link>
        </p>
      ) : (
        <form onSubmit={send} className="flex items-center gap-2 border-t border-border p-3">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={2000}
            placeholder="Написать…"
            aria-label="Сообщение продавцу"
            className="min-w-0 flex-1 rounded-lg bg-bg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent"
          />
          <button type="submit" disabled={busy || !text.trim()} aria-label="Отправить"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-accent-ink disabled:opacity-40">→</button>
        </form>
      )}
    </aside>
  );
}
