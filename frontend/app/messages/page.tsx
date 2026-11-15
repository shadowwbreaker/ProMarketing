"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { OrderChat } from "@/components/OrderChat";
import { Avatar } from "@/components/profile/Avatar";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { ConversationOrder, listConversations, PeerThread } from "@/lib/api/chat";
import { getOrder, Order, STATUS_LABEL } from "@/lib/api/orders";
import { getSeller } from "@/lib/api/public";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";
import { useLivePolling } from "@/lib/useLivePolling";

type Peer = PeerThread["user"];

function MessagesInner() {
  const { me, loading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const orderId = params.get("order");
  const requestedUser = orderId ? null : params.get("u");
  const [threads, setThreads] = useState<PeerThread[]>();
  const [extraPeer, setExtraPeer] = useState<Peer>();
  const [order, setOrder] = useState<Order>();
  const [peerOrders, setPeerOrders] = useState<{ peerId: string; orders: ConversationOrder[] }>();
  const [error, setError] = useState<string>();
  const [failedSelection, setFailedSelection] = useState<string>();

  const load = useCallback(async () => {
    if (!me) return;
    try {
      setThreads((await listConversations()).results);
      setError(undefined);
    } catch (e) {
      setError(fieldErrors(e).form ?? "Не удалось загрузить сообщения");
    }
  }, [me]);
  useLivePolling(load, 3000, "inbox-updated");
  useEffect(() => { if (!loading && !me) router.replace("/login"); }, [loading, me, router]);

  const selectedOrder = order?.id === orderId ? order : undefined;
  const orderPeer = selectedOrder && (selectedOrder.role === "seller" ? selectedOrder.buyer : selectedOrder.seller);
  const userId = orderPeer?.id ?? requestedUser;
  const selection = orderId ?? userId;
  const listedPeer = threads?.find((thread) => thread.user.id === userId)?.user;
  const hasListedPeer = Boolean(listedPeer);
  const peer = listedPeer ?? orderPeer ?? (extraPeer?.id === userId ? extraPeer : undefined);

  useEffect(() => {
    if (!me || !selection) return;
    let active = true;
    const fail = () => { if (active) setFailedSelection(selection); };
    if (orderId) {
      void getOrder(orderId).then((o) => {
        if (!active) return;
        if (!o.paid_at || o.role === "staff") fail();
        else setOrder(o);
      }).catch(fail);
    } else if (requestedUser && !hasListedPeer) {
      void getSeller(requestedUser).then((s) => {
        if (active) setExtraPeer({ id: s.id, display_name: s.display_name, avatar_url: s.avatar_url, online: s.online,
          date_joined: s.member_since, blocked: false });
      }).catch(fail);
    }
    return () => { active = false; };
  }, [me, orderId, selection, requestedUser, hasListedPeer]);

  const onOrders = useCallback((peerId: string, orders: ConversationOrder[]) => setPeerOrders({ peerId, orders }), []);
  if (!threads) return error ? <ErrorState message={error} /> : <LoadingState />;
  const orders = peerOrders?.peerId === peer?.id ? peerOrders?.orders ?? [] : [];
  const linkedOrder = selectedOrder?.id ?? orders[0]?.id;

  return (
    <div className="grid h-[calc(100dvh-8rem)] min-h-[30rem] overflow-hidden rounded-xl border border-border bg-surface md:grid-cols-[240px_minmax(0,1fr)] lg:grid-cols-[255px_minmax(0,1fr)_205px]">
      <section className={`min-h-0 min-w-0 flex-col border-border md:flex md:border-r ${selection ? "hidden" : "flex"}`}>
        <h1 className="border-b border-border px-5 py-5 text-2xl font-extrabold">Сообщения</h1>
        <ul className="min-h-0 flex-1 divide-y divide-border overflow-y-auto overscroll-contain">
          {!threads.length && <li className="px-5 py-4 text-sm text-muted">Здесь появятся ваши переписки.</li>}
          {threads.map((t) => {
            const selected = t.user.id === userId;
            return (
              <li key={t.user.id}>
                <Link href={`/messages?u=${t.user.id}`} aria-current={selected ? "true" : undefined}
                  className={`flex gap-3 px-4 py-3 ${selected ? "bg-accent/10" : "hover:bg-bg"}`}>
                  <Avatar id={t.user.id} name={t.user.display_name} size={40} src={t.user.avatar_url} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-1.5">
                      <b className="truncate text-sm">{t.user.display_name}</b>
                      <time dateTime={t.last_message_at} className="shrink-0 text-xs text-muted">
                        {new Date(t.last_message_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" })}
                      </time>
                    </div>
                    <p className="line-clamp-2 break-words text-sm text-muted">{t.last_message}</p>
                  </div>
                  {t.unread && <span className="mt-1 size-2.5 shrink-0 rounded-full bg-danger" aria-label="Непрочитанные сообщения" />}
                </Link>
              </li>
            );
          })}
        </ul>
      </section>

      <section className={`min-h-0 min-w-0 flex-col md:flex ${selection ? "flex" : "hidden"}`}>
        {selection && (
          <div className="flex shrink-0 items-center gap-2 border-b border-border p-3 sm:gap-3 sm:px-5">
            <Link href="/messages" className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-bg text-xl md:hidden" aria-label="Ко всем сообщениям">‹</Link>
            {peer && <>
              <Avatar id={peer.id} name={peer.display_name} size={40} src={peer.avatar_url} />
              <div className="min-w-0 flex-1">
                <Link href={`/sellers/${peer.id}`} className="block truncate font-bold hover:text-accent">{peer.display_name}</Link>
                <p className={`text-xs ${peer.online ? "text-ok" : "text-muted"}`}>{peer.blocked ? "Заблокирован" : peer.online ? "Онлайн" : "Не в сети"}</p>
              </div>
            </>}
            {linkedOrder && <Link href={`/orders/${linkedOrder}`} className="ml-auto shrink-0 rounded-lg bg-accent/10 px-2 py-2 text-xs font-semibold text-accent hover:underline sm:px-3 sm:text-sm">Детали заказа</Link>}
          </div>
        )}
        {peer ? <OrderChat key={selection} peerId={peer.id} orderId={selectedOrder?.id} onOrders={onOrders} /> :
          <p className="m-auto px-6 text-center text-sm text-muted">
            {selection === failedSelection ? "Переписка недоступна" : selection ? "Загружаем переписку…" : "Выберите переписку слева"}
          </p>}
      </section>

      <aside className="hidden min-h-0 min-w-0 overflow-y-auto border-l border-border px-5 py-5 lg:block">
        {peer && <>
          <p className="text-xs font-semibold text-muted">Дата регистрации</p>
          <p className="mt-1 text-sm">{formatDateTime(peer.date_joined)}</p>
          <Link href={`/sellers/${peer.id}`} className="mt-3 inline-block text-sm font-semibold text-accent hover:underline">Открыть профиль</Link>
        </>}
        {orders.length > 0 && <div className="mt-5 border-t border-border pt-5 text-sm">
          <h2 className="font-semibold">Заказы с собеседником</h2>
          <ul className="mt-2 space-y-3">
            {orders.map((o) => <li key={o.id}>
              <Link href={`/orders/${o.id}`} className="font-semibold text-accent hover:underline">#{o.id.slice(0, 8)}</Link>
              {o.title && <p className="break-words">{o.title}</p>}
              <p className="text-xs text-muted">{STATUS_LABEL[o.status] ?? o.status}</p>
            </li>)}
          </ul>
        </div>}
      </aside>
    </div>
  );
}

export default function MessagesPage() {
  return <Suspense fallback={<LoadingState />}><MessagesInner /></Suspense>;
}
