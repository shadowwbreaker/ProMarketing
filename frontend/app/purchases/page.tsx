"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { MineList } from "@/app/account/MineList";
import { STATUS_LABEL } from "@/lib/api/orders";
import { useAuth } from "@/lib/auth/AuthProvider";
import { formatDateTime, formatMoney } from "@/lib/format";

type OrderBrief = { id: string; status: string; total_minor: number; currency: string; created_at: string; items_count: number };

const TONE: Record<string, string> = {
  COMPLETED: "bg-ok/10 text-ok", CANCELLED: "bg-bg text-muted", REFUNDED: "bg-bg text-muted",
  DISPUTED: "bg-danger/10 text-danger", PARTIALLY_REFUNDED: "bg-warn/10 text-warn",
};

export default function PurchasesPage() {
  const { me, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !me) router.replace("/login");
  }, [loading, me, router]);
  if (!me) return null;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-3xl font-extrabold tracking-tight">Мои покупки</h1>
        <Link href="/catalog" className="text-sm font-semibold text-accent hover:underline">Найти канал для рекламы →</Link>
      </div>
      <MineList<OrderBrief>
        path="purchases"
        empty="Покупок пока нет"
        render={(o) => (
          <Link href={`/orders/${o.id}`} className="flex flex-wrap items-center justify-between gap-3">
            <span>
              <span className="block font-semibold">Заказ от {formatDateTime(o.created_at)}</span>
              <span className="text-sm text-muted">позиций: {o.items_count}</span>
            </span>
            <span className="flex items-center gap-3">
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONE[o.status] ?? "bg-accent/10 text-accent"}`}>{STATUS_LABEL[o.status] ?? o.status}</span>
              <span className="font-bold tabular-nums">{formatMoney(o.total_minor, o.currency)}</span>
            </span>
          </Link>
        )}
      />
    </div>
  );
}
