"use client";

import Link from "next/link";
import { useState } from "react";
import { SearchBar, StaffTable } from "@/components/StaffTable";
import { STATUS_LABEL } from "@/lib/api/orders";
import { formatDateTime, formatMoney } from "@/lib/format";

export default function StaffOrders() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [disputed, setDisputed] = useState("");
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Заказы</h1>
      <div className="flex flex-wrap gap-2">
        <SearchBar value={q} onChange={setQ} placeholder="ID заказа или email, Enter" />
        <select aria-label="Статус" value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-border bg-surface px-2 text-sm">
          <option value="">Все статусы</option>
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={disputed === "1"} onChange={(e) => setDisputed(e.target.checked ? "1" : "")} /> со спорами</label>
      </div>
      <StaffTable path="/staff/orders" params={{ q, status, disputed }} columns={[
        { title: "Создан", render: (o) => <Link className="text-accent" href={`/orders/${o.id}`}>{formatDateTime(o.created_at)}</Link> },
        { title: "Статус", render: (o) => STATUS_LABEL[o.status] ?? o.status },
        { title: "Сумма", render: (o) => formatMoney(o.total_minor) },
        { title: "Оплата", render: (o) => o.payment ?? "—" },
        { title: "Покупатель", render: (o) => o.buyer },
        { title: "Продавец", render: (o) => o.seller },
        { title: "Позиций", render: (o) => o.items },
      ]} />
    </div>
  );
}
