"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";
import { apiFetch } from "@/lib/api/client";
import { formatCount, formatMoney } from "@/lib/format";

type Dash = Record<string, number> & { finance?: { payments_minor: number; refunds_minor: number; payouts_paid_minor: number; platform_fee_minor: number; provider: string } };

const LABELS: [string, string][] = [
  ["users", "Пользователей"], ["sellers", "Продавцов"], ["buyers", "Покупателей"], ["blocked_users", "Заблокировано"],
  ["accounts", "Рекламных аккаунтов"], ["listed_accounts", "В каталоге"], ["accounts_under_review", "На проверке"], ["networks", "Сеток"],
  ["active_orders", "Активных заказов"], ["completed_orders", "Завершённых"], ["cancelled_orders", "Отмен и возвратов"],
  ["open_disputes", "Открытых споров"], ["orders_last_7d", "Заказов за 7 дней"],
];

export default function StaffDashboard() {
  const [d, setD] = useState<Dash>();
  useEffect(() => void apiFetch<Dash>("/staff/dashboard").then(setD), []);
  if (!d) return <LoadingState />;
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Обзор платформы</h1>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {LABELS.map(([k, label]) => (
          <Card key={k}><p className="text-xs text-muted">{label}</p><p className="text-2xl font-bold">{formatCount(d[k] ?? 0)}</p></Card>
        ))}
      </div>
      {d.finance && (
        <>
          <h2 className="text-lg font-bold">Финансы (подтверждённые провайдером, {d.finance.provider})</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card><p className="text-xs text-muted">Оплачено</p><p className="text-xl font-bold">{formatMoney(d.finance.payments_minor)}</p></Card>
            <Card><p className="text-xs text-muted">Возвращено</p><p className="text-xl font-bold">{formatMoney(d.finance.refunds_minor)}</p></Card>
            <Card><p className="text-xs text-muted">Выплачено продавцам</p><p className="text-xl font-bold">{formatMoney(d.finance.payouts_paid_minor)}</p></Card>
            <Card><p className="text-xs text-muted">Комиссия платформы</p><p className="text-xl font-bold">{formatMoney(d.finance.platform_fee_minor)}</p></Card>
          </div>
        </>
      )}
    </div>
  );
}
