"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import type { Page } from "@/lib/api/auth";
import { apiFetch } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";
import { useLivePolling } from "@/lib/useLivePolling";

type CaseRow = { id: string; order_number: string; reason: string; status: string; referred_at: string };

export function ArbitrationAccess({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <LoadingState />;
  if (!me?.permissions.includes("arbitration.work")) return <p role="alert">Раздел доступен арбитрам.</p>;
  return children;
}

export function ArbitrationQueue() {
  return <ArbitrationAccess><Queue /></ArbitrationAccess>;
}

function Queue() {
  const router = useRouter();
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<Page<CaseRow>>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    try {
      setRows(await apiFetch<Page<CaseRow>>("/staff/arbitration?" + new URLSearchParams({
        scope: mine ? "mine" : "queue", page: String(page),
      })));
    } catch (ex) {
      setError(fieldErrors(ex).form ?? "Не удалось загрузить заказы.");
    }
  }, [mine, page]);
  useLivePolling(load, 10000);

  async function claim(id: string) {
    setError("");
    setBusy(id);
    try {
      await apiFetch("/staff/arbitration/" + id + "/claim", { method: "POST" });
      router.push("/staff/orders/" + id);
    } catch (ex) {
      setError(fieldErrors(ex).form ?? "Не удалось взять заказ в работу.");
      void load();
    } finally { setBusy(""); }
  }

  const rowClass = "block w-full px-4 py-3 text-left hover:bg-bg";
  return <section className="grid gap-4">
    <h1 className="text-2xl font-bold">Заказы на арбитраже</h1>
    <div className="flex gap-2">
      {[[false, "Очередь"], [true, "Мои заказы"]].map(([value, title]) => (
        <Button type="button" key={String(value)} aria-pressed={mine === value} variant={mine === value ? "primary" : "secondary"}
          onClick={() => { if (mine !== value) { setRows(undefined); setError(""); setPage(1); setMine(Boolean(value)); } }}>
          {title}
        </Button>
      ))}
    </div>
    {error && <ErrorState message={error} />}
    {!rows && !error && <LoadingState />}
    {rows && (rows.results.length ? <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
      {rows.results.map((item) => {
        const info = <><strong>Заказ #{item.order_number} · {item.reason}</strong>
          <span className="block text-sm text-muted">{item.status} · {formatDateTime(item.referred_at)}</span></>;
        return <li key={item.id}>{mine ?
          <Link className={rowClass} href={"/staff/orders/" + item.id}>{info}</Link> :
          <button type="button" className={rowClass} disabled={!!busy} onClick={() => void claim(item.id)}>{info}</button>}
        </li>;
      })}
    </ul> : <EmptyState title={mine ? "Назначенных заказов нет" : "В очереди пока нет заказов"} />)}
    {rows && (rows.previous || rows.next) && <div className="flex justify-between">
      <Button type="button" variant="secondary" disabled={!rows.previous} onClick={() => setPage(page - 1)}>Назад</Button>
      <Button type="button" variant="secondary" disabled={!rows.next} onClick={() => setPage(page + 1)}>Дальше</Button>
    </div>}
  </section>;
}
