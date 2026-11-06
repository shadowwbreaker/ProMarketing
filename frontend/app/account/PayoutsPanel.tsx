"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { listPayouts, PAYOUT_LABEL, PayoutRow, retryPayout, withdrawPayout } from "@/lib/api/orders";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

export function PayoutsPanel() {
  const toast = useToast();
  const [rows, setRows] = useState<PayoutRow[]>();
  const load = () => listPayouts().then(setRows);
  useEffect(() => void load(), []);
  if (!rows) return <LoadingState />;
  if (!rows.length) return <EmptyState title="Выплат пока нет">Выплата появляется после подтверждения заказа покупателем и становится доступна через 48 часов.</EmptyState>;
  const act = (fn: () => Promise<PayoutRow>) => fn().then(load).catch((e) => toast(fieldErrors(e).form ?? "Ошибка", "error"));
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
      {rows.map((p) => (
        <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
          <span>
            <Link href={`/orders/${p.order}`} className="hover:text-accent">{p.account}</Link> · <b>{formatMoney(p.amount_minor)}</b> ·{" "}
            {PAYOUT_LABEL[p.status] ?? p.status}{p.status === "hold" && ` до ${formatDateTime(p.available_at)}`}
          </span>
          {p.status === "available" && <Button onClick={() => act(() => withdrawPayout(p.id))}>Вывести</Button>}
          {p.status === "failed" && <Button variant="secondary" onClick={() => act(() => retryPayout(p.id))}>Повторить</Button>}
        </li>
      ))}
    </ul>
  );
}
