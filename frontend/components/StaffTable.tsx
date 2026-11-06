"use client";

import { ReactNode, useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { apiFetch } from "@/lib/api/client";
import { fieldErrors } from "@/lib/forms";

/* eslint-disable @typescript-eslint/no-explicit-any */
export function StaffTable({ path, params, columns, nonce = 0 }: {
  path: string; params: Record<string, string>; nonce?: number;
  columns: { title: string; render: (row: any) => ReactNode }[];
}) {
  const [rows, setRows] = useState<any[]>();
  const [count, setCount] = useState(0);
  const [err, setErr] = useState<string>();
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  useEffect(() => {
    setRows(undefined);
    apiFetch<{ count: number; results: any[] }>(`${path}${qs ? `?${qs}` : ""}`)
      .then((r) => { setRows(r.results); setCount(r.count); })
      .catch((e) => setErr(fieldErrors(e).form));
  }, [path, qs, nonce]);
  if (err) return <ErrorState message={err} />;
  if (!rows) return <LoadingState />;
  if (!rows.length) return <EmptyState title="Ничего не найдено" />;
  return (
    <div className="overflow-x-auto">
      <p className="mb-1 text-xs text-muted">Найдено: {count}</p>
      <table className="w-full text-sm">
        <thead className="text-left text-muted"><tr>{columns.map((c) => <th key={c.title} className="pr-3">{c.title}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={r.id ?? r.seq ?? i} className="border-t border-border align-top">{columns.map((c) => <td key={c.title} className="py-1 pr-3">{c.render(r)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export function SearchBar({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return <input aria-label={placeholder} placeholder={placeholder} defaultValue={value} onKeyDown={(e) => e.key === "Enter" && onChange((e.target as HTMLInputElement).value)}
    className="w-full max-w-sm rounded-lg border border-border bg-surface px-3 py-2 text-sm" />;
}
