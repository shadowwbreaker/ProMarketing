"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Avatar } from "@/components/profile/Avatar";
import { Conversation } from "@/components/profile/Conversation";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { DirectThread, listDirect } from "@/lib/api/direct";
import { getSeller } from "@/lib/api/public";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, timeAgo } from "@/lib/format";

type Peer = DirectThread["user"];

function listDate(iso: string) {
  const d = new Date(iso);
  return d.toDateString() === new Date().toDateString()
    ? d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

function MessagesInner() {
  const { me, loading } = useAuth();
  const router = useRouter();
  const selected = useSearchParams().get("u");
  const [threads, setThreads] = useState<DirectThread[]>();
  const [extra, setExtra] = useState<Peer>();
  const [err, setErr] = useState<string>();

  const load = useCallback(() => {
    listDirect().then((r) => setThreads(r.results)).catch((e) => setErr(fieldErrors(e).form));
  }, []);
  useEffect(() => {
    if (!loading && !me) router.replace("/login");
    if (me) load();
  }, [loading, me, router, load]);

  const peer = threads?.find((t) => t.user.id === selected)?.user ?? (extra?.id === selected ? extra : undefined);
  // New conversation opened from a link (no messages yet): fetch the person's public card.
  useEffect(() => {
    if (!selected || !threads || threads.some((t) => t.user.id === selected)) return;
    getSeller(selected)
      .then((s) => setExtra({ id: s.id, display_name: s.display_name, avatar_url: s.avatar_url, online: s.online, date_joined: s.member_since, blocked: false }))
      .catch(() => setExtra(undefined));
  }, [selected, threads]);

  if (err) return <ErrorState message={err} />;
  if (!threads) return <LoadingState />;

  return (
    <div className="grid h-[calc(100dvh-9rem)] min-h-[30rem] overflow-hidden rounded-xl border border-border md:grid-cols-[280px_1fr] lg:grid-cols-[280px_1fr_240px]">
      {/* thread list */}
      <section className={`min-h-0 flex-col border-border md:flex md:border-r ${selected ? "hidden" : "flex"}`}>
        <h1 className="px-5 py-5 text-3xl font-extrabold">Сообщения</h1>
        <ul className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          {threads.length === 0 && <li className="px-5 text-sm text-muted">Здесь появятся переписки с продавцами и покупателями до оплаты. Чат по заказу — на странице заказа.</li>}
          {threads.map((t) => {
            const on = t.user.id === selected;
            return (
              <li key={t.user.id}>
                <Link href={`/messages?u=${t.user.id}`} aria-current={on ? "true" : undefined}
                  className={`flex gap-3 px-4 py-3 ${on ? "bg-accent text-accent-ink" : "hover:bg-bg"}`}>
                  <Avatar id={t.user.id} name={t.user.display_name} size={44} src={t.user.avatar_url} />
                  <div className="min-w-0 flex-1">
                    <p className="flex justify-between gap-2 text-sm">
                      <b className="truncate">{t.user.display_name}</b>
                      <span className={`shrink-0 text-xs ${on ? "" : "text-muted"}`}>{listDate(t.last_message_at)}</span>
                    </p>
                    <p className={`line-clamp-2 text-sm ${on ? "" : "text-muted"}`}>{t.last_message}</p>
                  </div>
                  {t.unread > 0 && !on && <span className="self-center rounded-full bg-accent px-2 text-xs font-bold text-accent-ink">{t.unread}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </section>

      {/* conversation */}
      <section className={`min-h-0 flex-col md:flex ${selected ? "flex" : "hidden"}`}>
        {peer ? (
          <>
            <div className="flex items-center gap-3 border-b border-border px-5 py-3">
              <Link href="/messages" className="text-xl text-muted md:hidden" aria-label="Ко всем сообщениям">‹</Link>
              <Link href={`/sellers/${peer.id}`}><Avatar id={peer.id} name={peer.display_name} size={44} src={peer.avatar_url} /></Link>
              <div className="min-w-0">
                <Link href={`/sellers/${peer.id}`} className="block truncate font-bold hover:text-accent">{peer.display_name}</Link>
                <p className={`text-sm ${peer.blocked ? "text-danger" : peer.online ? "text-ok" : "text-muted"}`}>
                  {peer.blocked ? "Заблокирован" : peer.online ? "Онлайн" : "Не в сети"}
                </p>
              </div>
            </div>
            <Conversation userId={peer.id} otherName={peer.display_name} onSent={load}
              empty={<p className="text-sm text-muted">Напишите первое сообщение</p>} />
          </>
        ) : (
          <p className="m-auto px-6 text-center text-sm text-muted">Выберите переписку слева</p>
        )}
      </section>

      {/* about the person */}
      <aside className="hidden border-l border-border px-6 py-5 lg:block">
        {peer && (
          <>
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted">Дата регистрации</p>
            <p className="mt-2 text-sm">{formatDateTime(peer.date_joined)}</p>
            <p className="text-sm text-muted">{timeAgo(peer.date_joined)}</p>
            <Link href={`/sellers/${peer.id}`} className="mt-5 inline-block text-sm font-semibold text-accent hover:underline">Открыть профиль</Link>
          </>
        )}
      </aside>
    </div>
  );
}

export default function MessagesPage() {
  return <Suspense><MessagesInner /></Suspense>;
}
