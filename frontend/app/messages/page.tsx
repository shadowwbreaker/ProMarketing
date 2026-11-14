"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { OrderChat } from "@/components/OrderChat";
import { Avatar } from "@/components/profile/Avatar";
import { Conversation } from "@/components/profile/Conversation";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { listOrderThreads, OrderThread } from "@/lib/api/chat";
import { DirectThread, listDirect } from "@/lib/api/direct";
import { getOrder, Order, STATUS_LABEL } from "@/lib/api/orders";
import { getSeller } from "@/lib/api/public";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

function MessagesInner() {
  const { me, loading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const orderId = params.get("order");
  const userId = orderId ? null : params.get("u");
  const [threads, setThreads] = useState<{ direct: DirectThread[]; orders: OrderThread[] }>();
  const [directPeer, setDirectPeer] = useState<DirectThread["user"]>();
  const [order, setOrder] = useState<Order>();
  const [error, setError] = useState<string>();
  const [selectionError, setSelectionError] = useState<string>();

  const load = useCallback(() => {
    void Promise.all([listDirect(), listOrderThreads()]).then(([direct, orders]) => {
      setThreads({ direct: direct.results, orders: orders.results });
      setError(undefined);
    }).catch((e) => setError(fieldErrors(e).form ?? "Не удалось загрузить сообщения"));
  }, []);
  useEffect(() => {
    if (!loading && !me) router.replace("/login");
    if (!me) return;
    load();
    const timer = window.setInterval(() => { if (!document.hidden) load(); }, 10000);
    return () => window.clearInterval(timer);
  }, [loading, me, router, load]);

  const listedPeer = threads?.direct.find((t) => t.user.id === userId)?.user;
  useEffect(() => {
    setSelectionError(undefined);
    if (!me || (!orderId && (!userId || listedPeer))) return;
    let active = true;
    const fail = () => { if (active) setSelectionError("Переписка недоступна"); };
    if (orderId) {
      void getOrder(orderId).then((o) => {
        if (!active) return;
        if (!o.paid_at || o.role === "staff") fail();
        else setOrder(o);
      }).catch(fail);
    } else if (userId) {
      void getSeller(userId).then((s) => {
        if (active) setDirectPeer({ id: s.id, display_name: s.display_name, avatar_url: s.avatar_url,
          online: s.online, date_joined: s.member_since, blocked: false });
      }).catch(fail);
    }
    return () => { active = false; };
  }, [me, orderId, userId, listedPeer]);

  if (!threads) return error ? <ErrorState message={error} /> : <LoadingState />;
  const rows = [
    ...threads.direct.map((t) => ({ ...t, href: `/messages?u=${t.user.id}`, selected: userId === t.user.id, label: "" })),
    ...threads.orders.map((t) => ({ ...t, href: `/messages?order=${t.order_id}`, selected: orderId === t.order_id,
      label: `Заказ #${t.order_id.slice(0, 8)} · ${t.brand}` })),
  ].sort((a, b) => Date.parse(b.last_message_at) - Date.parse(a.last_message_at));
  const selectedOrder = orderId && order?.id === orderId ? order : undefined;
  const peer = selectedOrder ? (selectedOrder.role === "seller" ? selectedOrder.buyer : selectedOrder.seller) :
    listedPeer ?? (directPeer?.id === userId ? directPeer : undefined);
  const selected = Boolean(orderId || userId);

  return (
    <div className="grid h-[calc(100dvh-8rem)] min-h-[30rem] overflow-hidden rounded-xl border border-border bg-surface md:grid-cols-[240px_minmax(0,1fr)] lg:grid-cols-[255px_minmax(0,1fr)_205px]">
      <section className={`min-h-0 min-w-0 flex-col border-border md:flex md:border-r ${selected ? "hidden" : "flex"}`}>
        <h1 className="border-b border-border px-5 py-5 text-2xl font-extrabold">Сообщения</h1>
        <ul className="min-h-0 flex-1 divide-y divide-border overflow-y-auto overscroll-contain">
          {!rows.length && <li className="px-5 py-4 text-sm text-muted">Здесь появятся ваши переписки и чаты по оплаченным заказам.</li>}
          {rows.map((t) => (
            <li key={t.href}>
              <Link href={t.href} aria-current={t.selected ? "true" : undefined}
                className={`flex gap-3 px-4 py-3 ${t.selected ? "bg-accent/10" : "hover:bg-bg"}`}>
                <Avatar id={t.user.id} name={t.user.display_name} size={40} src={t.user.avatar_url} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-1.5">
                    <b className="truncate text-sm">{t.user.display_name}</b>
                    <time dateTime={t.last_message_at} className="shrink-0 text-xs text-muted">
                      {new Date(t.last_message_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" })}
                    </time>
                  </div>
                  {t.label && <p className="truncate text-xs font-medium text-accent">{t.label}</p>}
                  <p className="line-clamp-2 break-words text-sm text-muted">{t.last_message}</p>
                </div>
                {t.unread > 0 && <span className="mt-1 size-2.5 shrink-0 rounded-full bg-danger" aria-label="Непрочитанные сообщения" />}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className={`min-h-0 min-w-0 flex-col md:flex ${selected ? "flex" : "hidden"}`}>
        {selected && (
          <div className="flex shrink-0 items-center gap-3 border-b border-border p-3 sm:px-5">
            <Link href="/messages" className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-bg text-xl md:hidden" aria-label="Ко всем сообщениям">‹</Link>
            {peer && <>
              <Avatar id={peer.id} name={peer.display_name} size={40} src={peer.avatar_url} />
              <div className="min-w-0 flex-1">
                <Link href={`/sellers/${peer.id}`} className="block truncate font-bold hover:text-accent">{peer.display_name}</Link>
                <p className={`text-xs ${peer.online ? "text-ok" : "text-muted"}`}>{peer.blocked ? "Заблокирован" : peer.online ? "Онлайн" : "Не в сети"}</p>
              </div>
            </>}
            {selectedOrder && <Link href={`/orders/${selectedOrder.id}`} className="ml-auto shrink-0 rounded-lg bg-accent/10 px-3 py-2 text-sm font-semibold text-accent hover:underline">Детали заказа</Link>}
          </div>
        )}
        {selectedOrder ? <OrderChat key={selectedOrder.id} orderId={selectedOrder.id} role={selectedOrder.role} onRead={load} /> :
          peer && userId ? <Conversation key={userId} userId={userId} otherName={peer.display_name} onSent={load}
            empty={<p className="text-sm text-muted">Напишите первое сообщение</p>} /> :
          <p className="m-auto px-6 text-center text-sm text-muted">
            {selectionError ?? (selected ? "Загружаем переписку…" : "Выберите переписку слева")}
          </p>}
      </section>

      <aside className="hidden min-w-0 border-l border-border px-5 py-5 lg:block">
        {peer && <>
          <p className="text-xs font-semibold text-muted">Дата регистрации</p>
          <p className="mt-1 text-sm">{formatDateTime(peer.date_joined)}</p>
          <Link href={`/sellers/${peer.id}`} className="mt-3 inline-block text-sm font-semibold text-accent hover:underline">Открыть профиль</Link>
        </>}
        {selectedOrder && <div className="mt-5 border-t border-border pt-5 text-sm">
          <p className="font-semibold">Заказ #{selectedOrder.id.slice(0, 8)}</p>
          <p className="mt-1 break-words text-muted">{STATUS_LABEL[selectedOrder.status] ?? selectedOrder.status}</p>
          <p className="mt-1 font-semibold">{formatMoney(selectedOrder.total_minor, selectedOrder.currency)}</p>
        </div>}
      </aside>
    </div>
  );
}

export default function MessagesPage() {
  return <Suspense fallback={<LoadingState />}><MessagesInner /></Suspense>;
}
