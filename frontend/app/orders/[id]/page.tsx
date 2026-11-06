"use client";

import { useParams, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { DisputePanel } from "@/components/DisputePanel";
import { OrderChat } from "@/components/OrderChat";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import {
  decideTerms,
  getOrder,
  getOrderEvents,
  Item,
  itemAction,
  mockComplete,
  Order,
  orderAction,
  OrderEvent,
  PAYOUT_LABEL,
  startPayment,
  STATUS_LABEL,
} from "@/lib/api/orders";
import { PLATFORM_LABEL } from "@/lib/api/social";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

function Deadline({ label, at }: { label: string; at: string | null }) {
  if (!at) return null;
  const past = new Date(at) < new Date();
  return <p className={`text-xs ${past ? "text-danger" : "text-muted"}`}>{label}: {formatDateTime(at)}{past && " (срок прошёл)"}</p>;
}

function ItemCard({ o, it, run }: { o: Order; it: Item; run: (fn: () => Promise<Order>, ok?: string) => Promise<void> }) {
  const buyer = o.role === "buyer";
  const seller = o.role === "seller";
  const proof = it.proofs[it.proofs.length - 1];

  function onProof(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const at = String(f.get("published_at") || "");
    void run(() => itemAction(o.id, it.id, "proof", {
      video_url: String(f.get("video_url")),
      published_at: (at ? new Date(at) : new Date()).toISOString(),
      notes: String(f.get("notes") ?? ""),
    }), "Ссылка на публикацию отправлена");
  }

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs text-muted">{PLATFORM_LABEL[it.account.platform]} · {it.account.ad_format_label}</p>
          <a href={it.account.profile_url} target="_blank" rel="noopener noreferrer nofollow" className="font-semibold hover:text-accent">
            {it.account.title} @{it.account.handle}
          </a>
        </div>
        <div className="text-right">
          <p className="font-bold">{formatMoney(it.price_minor)}</p>
          <p className="text-xs font-semibold" data-testid={`status-${it.id}`}>{STATUS_LABEL[it.status] ?? it.status}</p>
        </div>
      </div>
      {it.status === "AWAITING_SELLER_ACCEPTANCE" && <Deadline label="Продавец должен принять до" at={it.accept_deadline} />}
      {["IN_PROGRESS", "AWAITING_PUBLICATION"].includes(it.status) && <Deadline label="Опубликовать до" at={it.publish_deadline} />}
      {it.status === "AWAITING_BUYER_CONFIRMATION" && <Deadline label="Подтвердить до (иначе автоподтверждение после проверки)" at={it.confirm_deadline} />}
      {it.placement_until && <p className="text-xs text-muted">Публикация должна оставаться до {formatDateTime(it.placement_until)}</p>}
      {seller && <p className="text-xs text-muted">Вам после комиссии 5%: {formatMoney(it.seller_amount_minor)}</p>}
      {it.refunded_minor > 0 && <p className="text-xs text-warn">Возвращено покупателю: {formatMoney(it.refunded_minor)}</p>}
      {it.payout && (
        <p className="text-xs">Выплата продавцу: <b>{PAYOUT_LABEL[it.payout.status] ?? it.payout.status}</b>
          {it.payout.status === "hold" && ` до ${formatDateTime(it.payout.available_at)}`}</p>
      )}
      {proof && (
        <p className="text-sm">Публикация: <a href={proof.video_url} target="_blank" rel="noopener noreferrer nofollow" className="text-accent break-all">{proof.video_url}</a></p>
      )}
      {it.checks.length > 0 && (
        <p className="text-xs text-muted">Последняя проверка: {it.checks[0].result === "found" ? "видео доступно" : it.checks[0].result === "not_found" ? "видео не найдено" : "проверка недоступна"} ({formatDateTime(it.checks[0].checked_at)})</p>
      )}

      <div className="flex flex-wrap gap-2">
        {seller && it.status === "AWAITING_SELLER_ACCEPTANCE" && (
          <>
            <Button onClick={() => run(() => itemAction(o.id, it.id, "accept"), "Заказ принят")}>Принять заказ</Button>
            <Button variant="secondary" onClick={() => {
              const reason = prompt("Причина отказа");
              if (reason) void run(() => itemAction(o.id, it.id, "decline", { reason }), "Вы отказались, деньги возвращаются покупателю");
            }}>Отказаться</Button>
          </>
        )}
        {seller && it.status === "IN_PROGRESS" && (
          <Button variant="secondary" onClick={() => run(() => itemAction(o.id, it.id, "ready"))}>Видео готово, ждёт публикации</Button>
        )}
        {buyer && it.status === "AWAITING_SELLER_ACCEPTANCE" && (
          <Button variant="secondary" onClick={() => run(() => itemAction(o.id, it.id, "cancel"), "Заказ отменён, деньги возвращаются")}>Отменить и вернуть деньги</Button>
        )}
        {buyer && it.status === "AWAITING_BUYER_CONFIRMATION" && (
          <>
            <Button onClick={() => run(() => itemAction(o.id, it.id, "confirm"), "Выполнение подтверждено")}>Подтвердить выполнение</Button>
            <Button variant="secondary" onClick={() => {
              const comment = prompt("Что нужно исправить?");
              if (comment) void run(() => itemAction(o.id, it.id, "rework", { comment }));
            }}>Попросить исправить</Button>
          </>
        )}
        {buyer && proof && <Button variant="ghost" onClick={() => run(() => itemAction(o.id, it.id, "check-publication"), "Проверка запущена")}>Проверить публикацию</Button>}
      </div>

      {seller && ["IN_PROGRESS", "AWAITING_PUBLICATION"].includes(it.status) && (
        <form onSubmit={onProof} className="grid gap-2 border-t border-border pt-3 sm:grid-cols-[1fr_200px]">
          <input name="video_url" required placeholder="Ссылка на опубликованное видео" aria-label="Ссылка на видео" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
          <input name="published_at" type="datetime-local" aria-label="Дата публикации" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
          <input name="notes" placeholder="Комментарий (необязательно)" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm sm:col-span-2" />
          <Button type="submit" className="sm:col-span-2">Отправить ссылку на публикацию</Button>
        </form>
      )}
    </Card>
  );
}

function OrderPageInner() {
  const { id } = useParams<{ id: string }>();
  const q = useSearchParams();
  const mockPayment = q.get("mock_payment");
  const toast = useToast();
  const [o, setO] = useState<Order>();
  const [events, setEvents] = useState<OrderEvent[]>([]);
  const [err, setErr] = useState<string>();

  const load = useCallback(async () => {
    try {
      const [order, ev] = await Promise.all([getOrder(id), getOrderEvents(id)]);
      setO(order);
      setEvents(ev);
    } catch (e) {
      setErr(fieldErrors(e).form);
    }
  }, [id]);
  useEffect(() => void load(), [load]);

  const run = useCallback(async (fn: () => Promise<Order>, ok?: string) => {
    try {
      setO(await fn());
      if (ok) toast(ok, "success");
      void getOrderEvents(id).then(setEvents);
      setTimeout(() => void load(), 1500); // background checks/refunds may finish shortly after
    } catch (e) {
      toast(fieldErrors(e).form ?? "Ошибка", "error");
    }
  }, [id, load, toast]);

  if (err) return <ErrorState message={err} />;
  if (!o) return <LoadingState />;
  const t = o.terms;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px] [&>*]:min-w-0">
      <div className="flex flex-col gap-4">
        <div>
          <p className="text-sm text-muted">Заказ от {formatDateTime(o.created_at)} · {o.role === "buyer" ? `продавец ${o.seller.display_name}` : `покупатель ${o.buyer.display_name}`}</p>
          <h1 className="text-2xl font-bold">{STATUS_LABEL[o.status] ?? o.status} · {formatMoney(o.total_minor)}</h1>
          {o.role === "buyer" && o.seller.last_seen_at && <p className="text-xs text-muted">Продавец был на сайте {formatDateTime(o.seller.last_seen_at)}</p>}
        </div>

        {o.role === "buyer" && o.status === "AWAITING_PAYMENT" && (
          <Card className="border-accent">
            {mockPayment ? (
              <>
                <p className="mb-2 font-semibold">Тестовая оплата (платёжный провайдер ещё не подключён)</p>
                <p className="mb-3 text-sm text-muted">Это имитация страницы провайдера. Реальные деньги не списываются.</p>
                <div className="flex gap-2">
                  <Button onClick={async () => {
                    try {
                      await mockComplete(mockPayment, "succeeded");
                      toast("Оплата подтверждена провайдером", "success");
                      await load();
                    } catch (e) { toast(fieldErrors(e).form ?? "Ошибка", "error"); }
                  }}>Оплатить (тест)</Button>
                  <Button variant="secondary" onClick={() => mockComplete(mockPayment, "cancelled").then(load)}>Отменить оплату</Button>
                </div>
              </>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm">Оплатите заказ, чтобы продавец приступил к работе.</p>
                <div className="flex gap-2">
                  <Button onClick={async () => {
                    try {
                      const p = await startPayment(o.id);
                      window.location.href = p.confirmation_url;
                    } catch (e) { toast(fieldErrors(e).form ?? "Ошибка", "error"); }
                  }}>Перейти к оплате</Button>
                  <Button variant="ghost" onClick={() => run(() => orderAction(o.id, "cancel"), "Заказ отменён")}>Отменить</Button>
                </div>
              </div>
            )}
          </Card>
        )}

        {o.items.map((it) => <ItemCard key={it.id} o={o} it={it} run={run} />)}

        {o.proposals.filter((p) => p.status === "pending").map((p) => (
          <Card key={p.id} className="border-warn">
            <p className="font-semibold">Предложено изменить условия</p>
            <ul className="my-2 text-sm">{Object.entries(p.changes).map(([k, v]) => <li key={k}><b>{k}:</b> {String(v)}</li>)}</ul>
            {p.comment && <p className="text-sm text-muted">{p.comment}</p>}
            {((o.role === "buyer" && p.proposed_by === o.seller.id) || (o.role === "seller" && p.proposed_by === o.buyer.id)) ? (
              <div className="mt-2 flex gap-2">
                <Button onClick={() => run(() => decideTerms(o.id, p.id, true), "Условия изменены")}>Согласиться</Button>
                <Button variant="secondary" onClick={() => run(() => decideTerms(o.id, p.id, false))}>Отклонить</Button>
              </div>
            ) : <p className="mt-2 text-xs text-muted">Ждём ответа другой стороны</p>}
          </Card>
        ))}

        <DisputePanel order={o} onChanged={() => void load()} />

        <OrderChat orderId={o.id} role={o.role} />

        <Card>
          <h2 className="mb-2 font-bold">История заказа</h2>
          <ol className="grid gap-1 text-xs">
            {events.map((e) => (
              <li key={e.seq} className="flex gap-2"><span className="text-muted">{formatDateTime(e.created_at)}</span><span>{e.type}{e.to && ` → ${STATUS_LABEL[e.to] ?? e.to}`}</span></li>
            ))}
          </ol>
        </Card>
      </div>

      <aside className="flex flex-col gap-3">
        <Card>
          <h2 className="mb-2 font-bold">Условия (версия {t.version})</h2>
          <dl className="grid gap-2 text-sm">
            <div><dt className="text-xs text-muted">Бренд</dt><dd>{t.brand}</dd></div>
            <div><dt className="text-xs text-muted">ТЗ</dt><dd className="whitespace-pre-line">{t.brief}</dd></div>
            {Boolean(t.ad_text) && <div><dt className="text-xs text-muted">Текст</dt><dd className="whitespace-pre-line">{String(t.ad_text)}</dd></div>}
            {Boolean(t.cta) && <div><dt className="text-xs text-muted">CTA</dt><dd>{String(t.cta)}</dd></div>}
            <div><dt className="text-xs text-muted">Срок размещения</dt><dd>{t.placement_days} дней</dd></div>
          </dl>
          {o.role !== "staff" && o.paid_at && (
            <button className="mt-3 text-sm text-accent" onClick={() => {
              const brief = prompt("Новое ТЗ (изменение вступит в силу только после согласия другой стороны)", t.brief);
              if (brief && brief !== t.brief) void run(() => orderAction(o.id, "terms/propose", { changes: { brief } }), "Предложение отправлено");
            }}>Предложить изменить ТЗ</button>
          )}
        </Card>
        {o.role === "buyer" && o.paid_at && !o.materials_delivered_at && (
          <Button variant="secondary" onClick={() => run(() => orderAction(o.id, "materials-delivered"), "Продавец уведомлён")}>Я передал рекламные материалы</Button>
        )}
      </aside>
    </div>
  );
}

export default function OrderPage() {
  return <Suspense><OrderPageInner /></Suspense>;
}
