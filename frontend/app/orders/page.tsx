"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Avatar } from "@/components/profile/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { API_URL } from "@/lib/api/client";
import { listReceived, ReceivedOrders, STATUS_LABEL } from "@/lib/api/orders";
import { useAuth } from "@/lib/auth/AuthProvider";
import { formatDateTime, formatMoney } from "@/lib/format";

const control = "w-full min-w-0 rounded-lg border border-border bg-surface px-3 py-2 text-sm";
const receivedStatuses = Object.entries(STATUS_LABEL).filter(([status]) => !["DRAFT", "AWAITING_PAYMENT"].includes(status));

export default function OrdersPage() {
  const { me, loading } = useAuth();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<{ key: string; orders?: ReceivedOrders }>();
  const key = `${query}&page=${page}`;
  const orders = result?.key === key ? result.orders : undefined;

  useEffect(() => {
    if (loading) return;
    if (!me) {
      router.replace("/login");
      return;
    }
    let current = true;
    void listReceived(key).then((data) => {
      if (current) setResult({ key, orders: data });
    }).catch(() => { if (current) setResult({ key }); });
    return () => { current = false; };
  }, [key, loading, me, router]);

  function search(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const params = new URLSearchParams();
    for (const [name, value] of new FormData(e.currentTarget)) {
      if (typeof value === "string" && value.trim()) params.set(name, value.trim());
    }
    setPage(1);
    setQuery(params.toString());
  }

  if (loading || !me) return <LoadingState />;
  const s = orders?.summary;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-extrabold tracking-tight">Заказы</h1>
        {orders && orders.count > 0 && (
          <a href={`${API_URL}/api/v1/orders/received?format_csv=1&${query}`} className="rounded-lg border border-border px-4 py-2 text-sm font-semibold text-accent hover:bg-bg">Скачать CSV</a>
        )}
      </div>
      <form onSubmit={search} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1.25fr_1fr_auto]">
        <label className="space-y-1 text-xs font-semibold text-muted">Номер заказа<input name="number" className={control} placeholder="Номер или его начало" /></label>
        <label className="space-y-1 text-xs font-semibold text-muted">Покупатель<input name="buyer" className={control} placeholder="Имя покупателя" /></label>
        <label className="space-y-1 text-xs font-semibold text-muted">Статус<select name="status" className={control}><option value="">Все статусы</option>{receivedStatuses.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <label className="space-y-1 text-xs font-semibold text-muted">Платформа<select name="platform" className={control}><option value="">Все платформы</option><option value="youtube">YouTube</option><option value="tiktok">TikTok</option><option value="instagram">Instagram</option></select></label>
        <Button type="submit" className="self-end">Показать</Button>
      </form>

      {s && <section aria-labelledby="order-stats">
        <h2 id="order-stats" className="mb-3 text-xl font-bold">Статистика продаж</h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            ["Выплачено", formatMoney(s.earned_minor)],
            ["Всего заказов", s.total],
            ["Оборот", formatMoney(s.volume)],
            ["Средний чек", formatMoney(s.total ? Math.round(s.volume / s.total) : 0)],
            ["Выполнено", s.completed],
            ["В работе", s.active],
            ["Возвраты", `${s.refunds.orders} · ${formatMoney(s.refunds.amount_minor)}`],
            ["Покупатели", s.buyers],
          ].map(([label, value]) => (
            <Card key={label} className={label === "Выплачено" ? "bg-ok/5" : undefined}>
              <p className="text-xs font-medium text-muted">{label}</p>
              <p className="mt-1 break-words text-lg font-bold tabular-nums">{value}</p>
            </Card>
          ))}
        </div>
      </section>}

      {!orders ? (result?.key === key ? <ErrorState message="Не удалось загрузить заказы" /> : <LoadingState />) :
        !orders.count ? <Card><p className="text-sm text-muted">{query ? "Заказы по этим фильтрам не найдены." : "У вас пока нет оплаченных заказов от покупателей."}</p></Card> :
        <section aria-label="Список заказов" className="overflow-hidden rounded-xl border border-border bg-surface">
          <table className="block w-full text-left text-sm lg:table">
            <thead className="sr-only lg:not-sr-only">
              <tr className="border-b border-border bg-bg">
                {["Дата оплаты", "Заказ", "Описание", "Покупатель", "Статус", "Сумма"].map((label) =>
                  <th key={label} scope="col" className="px-4 py-3 font-semibold last:text-right">{label}</th>)}
              </tr>
            </thead>
            <tbody className="block divide-y divide-border lg:table-row-group">
              {orders.results.map((o) => (
                <tr key={o.id} className="grid min-w-0 grid-cols-2 items-start gap-2 p-4 hover:bg-bg lg:table-row lg:p-0 [&>td]:min-w-0 lg:[&>td]:px-4 lg:[&>td]:py-3">
                  <td className="break-words text-xs text-muted"><time dateTime={o.paid_at}>{formatDateTime(o.paid_at)}</time></td>
                  <td className="text-right lg:text-left"><Link href={`/orders/${o.id}`} className="font-semibold text-accent hover:underline" aria-label={`Открыть заказ ${o.id.slice(0, 8)}`}>#{o.id.slice(0, 8)}</Link></td>
                  <td className="col-span-2 break-words lg:max-w-xs"><Link href={`/orders/${o.id}`} className="font-semibold hover:text-accent">{o.title}</Link>{o.brand && <p className="text-xs text-muted">{o.brand}</p>}</td>
                  <td><Link href={`/sellers/${o.buyer.id}`} className="flex min-w-0 items-center gap-2 hover:text-accent"><Avatar id={o.buyer.id} name={o.buyer.display_name} size={28} src={o.buyer.avatar_url} /><span className="break-all">{o.buyer.display_name}</span></Link></td>
                  <td className="break-words font-medium text-muted">{STATUS_LABEL[o.status] ?? o.status}</td>
                  <td className="whitespace-nowrap font-bold tabular-nums lg:text-right">{formatMoney(o.total_minor, o.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(orders.previous || orders.next) && <nav aria-label="Страницы заказов" className="flex items-center justify-between gap-3 border-t border-border p-3">
            <Button variant="secondary" disabled={!orders.previous} onClick={() => setPage(page - 1)}>Назад</Button>
            <span className="text-sm text-muted">Страница {page}</span>
            <Button variant="secondary" disabled={!orders.next} onClick={() => setPage(page + 1)}>Дальше</Button>
          </nav>}
        </section>}
    </div>
  );
}
