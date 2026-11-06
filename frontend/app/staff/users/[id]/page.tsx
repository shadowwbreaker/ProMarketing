"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function StaffUser() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const toast = useToast();
  const [u, setU] = useState<any>();
  const load = useCallback(() => apiFetch<any>(`/staff/users/${id}`).then(setU), [id]);
  useEffect(() => void load(), [load]);
  if (!u) return <LoadingState />;
  const can = me?.permissions.includes("user.sanction");
  const act = (action: string) => {
    const reason = prompt("Основание");
    if (!reason) return;
    const days = action === "limit" ? prompt("На сколько дней? (пусто — бессрочно)") : null;
    apiFetch(`/staff/users/${id}/${action}`, { method: "POST", body: { reason, days: days || undefined } })
      .then(load).then(() => toast("Готово", "success")).catch((e) => toast(fieldErrors(e).form ?? "Ошибка", "error"));
  };
  const orders = (rows: any[]) => <ul className="text-sm">{rows.map((o) => <li key={o.id}><Link className="text-accent" href={`/orders/${o.id}`}>{formatDateTime(o.created_at)}</Link> · {o.status} · {formatMoney(o.total_minor)}</li>)}</ul>;
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">{u.display_name} <span className="text-base font-normal text-muted">{u.email}</span></h1>
      <p className="text-sm">Статус: <b>{u.status}</b> · роли: {u.roles.join(", ")} · email {u.is_email_verified ? "подтверждён" : "не подтверждён"} · был {u.last_seen_at ? formatDateTime(u.last_seen_at) : "—"}</p>
      {can && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => act("warning")}>Предупреждение</Button>
          <Button variant="secondary" onClick={() => act("limit")}>Ограничить</Button>
          <Button variant="danger" onClick={() => act("block")}>Заблокировать</Button>
          <Button variant="ghost" onClick={() => act("unblock")}>Разблокировать</Button>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <Card><h2 className="mb-1 font-bold">Покупки</h2>{orders(u.orders_as_buyer)}</Card>
        <Card><h2 className="mb-1 font-bold">Продажи</h2>{orders(u.orders_as_seller)}</Card>
        <Card><h2 className="mb-1 font-bold">Жалобы</h2><p className="text-sm">Открыл {u.disputes.opened}, отклонено {u.disputes.rejected}, против него {u.disputes.against}</p></Card>
        <Card><h2 className="mb-1 font-bold">Санкции</h2><ul className="text-sm">{u.sanctions.map((s: any) => <li key={s.id}>{s.type} · {s.reason} · {formatDateTime(s.starts_at)}{s.revoked_at && " (снята)"}</li>)}</ul></Card>
        <Card><h2 className="mb-1 font-bold">Аккаунты</h2><ul className="text-sm">{u.accounts.map((a: any) => <li key={a.id}><Link className="text-accent" href={`/staff/accounts?q=${a.handle}`}>{a.platform} @{a.handle}</Link> · {a.status}</li>)}</ul></Card>
        <Card><h2 className="mb-1 font-bold">История действий</h2><ul className="max-h-64 overflow-y-auto text-xs">{u.history.map((h: any, i: number) => <li key={i}>{formatDateTime(h.created_at)} · {h.action}</li>)}</ul></Card>
      </div>
    </div>
  );
}
