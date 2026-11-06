"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api/client";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";

type R = { id: string; rating: number; text: string; seller_reply: string; moderation_status: string; author: string; target: string; created_at: string; complaints: { id: string; reason: string; status: string; author: string }[] };

export default function StaffReviews() {
  const toast = useToast();
  const [onlyComplaints, setOnly] = useState(true);
  const [rows, setRows] = useState<R[]>();
  const load = useCallback(() => apiFetch<R[]>(`/staff/reviews${onlyComplaints ? "?complaints=1" : ""}`).then(setRows), [onlyComplaints]);
  useEffect(() => void load(), [load]);
  const act = (id: string, action: string) => {
    const comment = prompt("Комментарий модератора");
    if (comment) apiFetch(`/staff/reviews/${id}/${action}`, { method: "POST", body: { comment } }).then(load).catch((e) => toast(fieldErrors(e).form ?? "Ошибка", "error"));
  };
  if (!rows) return <LoadingState />;
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Модерация отзывов</h1>
      <label className="text-sm"><input type="checkbox" checked={onlyComplaints} onChange={(e) => setOnly(e.target.checked)} /> только с жалобами</label>
      {!rows.length && <EmptyState title="Нечего модерировать" />}
      {rows.map((r) => (
        <Card key={r.id}>
          <p className="text-sm"><b>{"★".repeat(r.rating)}</b> {r.text} <span className="text-xs text-muted">· {r.author} → {r.target} · {formatDateTime(r.created_at)} · {r.moderation_status}</span></p>
          {r.seller_reply && <p className="text-sm text-muted">Ответ: {r.seller_reply}</p>}
          <ul className="my-2 text-xs">{r.complaints.map((c) => <li key={c.id}>Жалоба ({c.author}, {c.status}): {c.reason}</li>)}</ul>
          <div className="flex gap-2">
            <Button variant="danger" onClick={() => act(r.id, "hide")}>Скрыть</Button>
            <Button variant="secondary" onClick={() => act(r.id, "keep")}>Оставить</Button>
            {r.moderation_status === "hidden" && <Button variant="ghost" onClick={() => act(r.id, "restore")}>Вернуть</Button>}
          </div>
        </Card>
      ))}
    </div>
  );
}
