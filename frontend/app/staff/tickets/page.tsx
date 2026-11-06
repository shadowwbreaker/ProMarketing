"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api/client";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";

type T = { id: string; subject: string; status: string; priority: string; author: string; assignee: string | null; created_at: string; messages: { body: string; is_staff_reply: boolean; created_at: string }[] };

export default function StaffTickets() {
  const toast = useToast();
  const [rows, setRows] = useState<T[]>();
  const load = () => apiFetch<T[]>("/staff/tickets").then(setRows);
  useEffect(() => void load(), []);
  const act = (id: string, action: string, body: Record<string, unknown> = {}) =>
    apiFetch(`/staff/tickets/${id}/${action}`, { method: "POST", body }).then(load).catch((e) => toast(fieldErrors(e).form ?? "Ошибка", "error"));
  if (!rows) return <LoadingState />;
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Обращения в поддержку</h1>
      {!rows.length && <EmptyState title="Очередь пуста" />}
      {rows.map((t) => (
        <Card key={t.id}>
          <p className="font-semibold">{t.subject} <span className="text-xs text-muted">· {t.author} · {formatDateTime(t.created_at)} · {t.status} · {t.priority}{t.assignee && ` · ${t.assignee}`}</span></p>
          <ul className="my-2 text-sm">{t.messages.map((m, i) => <li key={i} className={m.is_staff_reply ? "text-accent" : ""}>{m.is_staff_reply ? "Поддержка" : "Пользователь"}: {m.body}</li>)}</ul>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => act(t.id, "assign")}>Взять</Button>
            <Button variant="secondary" onClick={() => act(t.id, "priority", { priority: t.priority === "high" ? "normal" : "high" })}>Приоритет</Button>
            <Button onClick={() => { const b = prompt("Ответ"); if (b) void act(t.id, "reply", { body: b }); }}>Ответить</Button>
            <Button variant="ghost" onClick={() => act(t.id, "close")}>Закрыть</Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
