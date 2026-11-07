"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { apiFetch } from "@/lib/api/client";

type S = { type: string; severity: string; user: string | null; subject: string; detail: string };
const LABEL: Record<string, string> = {
  suspicious_stats: "Подозрительная статистика", repeated_false_complaints: "Повторные ложные жалобы", repeated_missed_deadlines: "Повторные нарушения сроков",
  off_platform_attempts: "Попытки увести сделку", review_manipulation: "Возможная накрутка отзывов", proof_link_changed: "Подмена ссылки на публикацию",
  many_open_disputes: "Много открытых жалоб",
};

export default function FraudSignals() {
  const [d, setD] = useState<{ results: S[]; note: string }>();
  const [err, setErr] = useState<string>();
  useEffect(() => void apiFetch<{ results: S[]; note: string }>("/staff/fraud-signals").then(setD).catch((e) => setErr(e instanceof Error ? e.message : "Ошибка")), []);
  if (err) return <ErrorState message={err} />;
  if (!d) return <LoadingState />;
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Антифрод-сигналы</h1>
      <p className="text-sm text-muted">{d.note}</p>
      {!d.results.length && <EmptyState title="Сигналов нет" />}
      {d.results.map((s, i) => (
        <Card key={i} className={s.severity === "high" ? "border-danger/50" : ""}>
          <p className="font-semibold">{LABEL[s.type] ?? s.type} <span className="text-xs text-muted">· {s.severity}</span></p>
          <p className="text-sm">{s.detail}</p>
          {s.user && <Link className="text-xs text-accent" href={`/staff/users/${s.user}`}>Открыть пользователя</Link>}
        </Card>
      ))}
    </div>
  );
}
