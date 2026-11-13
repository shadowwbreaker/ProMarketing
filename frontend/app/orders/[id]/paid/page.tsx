"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getOrder, Order } from "@/lib/api/orders";
import { getMeta } from "@/lib/api/meta";
import { formatMoney } from "@/lib/format";

/** "Payment confirmed" screen shown right after "Купить" in the beta (D-025). */
export default function PaidPage() {
  const { id } = useParams<{ id: string }>();
  const [o, setO] = useState<Order>();
  const [beta, setBeta] = useState(false);
  useEffect(() => {
    getOrder(id).then(setO).catch(() => {});
    void getMeta().then((m) => setBeta(m.beta));
  }, [id]);
  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-10 text-center">
      <div className="stagger flex flex-col items-center">
        <span className="flex h-20 w-20 items-center justify-center rounded-[32%] bg-gradient-to-br from-[#2bb673] to-[#19a05f] text-white shadow-lg">
          <svg aria-hidden width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
        </span>
        <h1 className="mt-6 text-3xl font-extrabold tracking-tight">Оплата подтверждена</h1>
        <p className="mt-3 text-muted">
          {o ? <>Заказ на {formatMoney(o.total_minor)} оплачен. </> : null}
          Продавец получил уведомление и примет заказ в течение 24 часов. Деньги удерживаются до тех пор, пока вы не подтвердите выполнение.
        </p>
        {beta && <p className="mt-3 rounded-lg bg-bg px-3 py-2 text-xs text-muted">Бета-версия: оплата имитирована, деньги не списаны.</p>}
        <Link href={`/orders/${id}#chat`} className="mt-7 rounded-xl bg-accent px-6 py-3 font-semibold text-accent-ink transition-[translate] duration-200 hover:-translate-y-0.5 motion-reduce:hover:translate-y-0">
          Вернуться к заказу и чату
        </Link>
        <Link href="/purchases" className="mt-3 text-sm text-muted hover:text-text">Все покупки</Link>
      </div>
    </div>
  );
}
