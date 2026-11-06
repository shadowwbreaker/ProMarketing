"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { DISPUTE_STATUS, staffQueue } from "@/lib/api/disputes";
import { formatDateTime, formatMoney } from "@/lib/format";

type Row = { id: string; status: string; priority: string; created_at: string; amount_minor: number; buyer: string; seller: string; reason: string; assignee: string | null; response_overdue: boolean; is_appeal: boolean; has_counterclaim: boolean };

export default function DisputeQueue() {
  const [filter, setFilter] = useState({ status: "", priority: "", assignee: "" });
  const [rows, setRows] = useState<Row[]>();
  useEffect(() => {
    const qs = new URLSearchParams(Object.entries(filter).filter(([, v]) => v)).toString();
    setRows(undefined);
    staffQueue(qs).then((r) => setRows(r.results as Row[]));
  }, [filter]);
  const sel = "rounded-lg border border-border bg-surface px-2 py-1 text-sm";
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Споры</h1>
      <div className="flex flex-wrap gap-2">
        <select aria-label="Статус" className={sel} value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
          <option value="">Все открытые</option>
          {Object.entries(DISPUTE_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select aria-label="Приоритет" className={sel} value={filter.priority} onChange={(e) => setFilter({ ...filter, priority: e.target.value })}>
          <option value="">Любой приоритет</option><option value="high">Высокий</option><option value="normal">Обычный</option>
        </select>
        <select aria-label="Назначение" className={sel} value={filter.assignee} onChange={(e) => setFilter({ ...filter, assignee: e.target.value })}>
          <option value="">Все</option><option value="me">Мои</option><option value="none">Не назначены</option>
        </select>
      </div>
      {!rows ? <LoadingState /> : !rows.length ? <EmptyState title="Споров нет" /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-muted"><tr><th>Открыт</th><th>Статус</th><th>Причина</th><th>Сумма</th><th>Покупатель</th><th>Продавец</th><th>Сотрудник</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-border">
                  <td><Link className="text-accent" href={`/staff/disputes/${r.id}`}>{formatDateTime(r.created_at)}</Link>{r.priority === "high" && " 🔺"}</td>
                  <td>{DISPUTE_STATUS[r.status]}{r.response_overdue && " · нет ответа"}{r.is_appeal && " · апелляция"}{r.has_counterclaim && " · встречная"}</td>
                  <td>{r.reason}</td><td>{formatMoney(r.amount_minor)}</td><td>{r.buyer}</td><td>{r.seller}</td><td>{r.assignee ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
