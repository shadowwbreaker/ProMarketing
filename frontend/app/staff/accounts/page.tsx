"use client";

import { useEffect, useState } from "react";
import { SearchBar, StaffTable } from "@/components/StaffTable";
import { TrustBadge } from "@/components/stats/TrustBadge";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api/client";
import { fieldErrors } from "@/lib/forms";
import { formatCount } from "@/lib/format";

export default function StaffAccounts() {
  const toast = useToast();
  const [q, setQ] = useState("");
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get("q");
    if (v) setQ(v);
  }, []);
  const [status, setStatus] = useState("");
  const [trust, setTrust] = useState("");
  const [nonce, setNonce] = useState(0);
  const act = (id: string, action: string) => {
    const reason = prompt("Основание");
    if (reason) apiFetch(`/staff/accounts/${id}/${action}`, { method: "POST", body: { reason } }).then(() => setNonce((n) => n + 1)).catch((e) => toast(fieldErrors(e).form ?? "Ошибка", "error"));
  };
  const sel = "rounded-lg border border-border bg-surface px-2 text-sm";
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Рекламные аккаунты</h1>
      <div className="flex flex-wrap gap-2">
        <SearchBar value={q} onChange={setQ} placeholder="@аккаунт, название или email владельца" />
        <select aria-label="Статус" className={sel} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Все статусы</option><option value="active">Активные</option><option value="under_review">На проверке</option><option value="blocked">Заблокированы</option><option value="hidden">Скрыты</option>
        </select>
        <select aria-label="Статистика" className={sel} value={trust} onChange={(e) => setTrust(e.target.value)}>
          <option value="">Любая статистика</option><option value="SUSPICIOUS">Подозрительная</option><option value="MANUAL">Ручная</option><option value="VERIFIED">Подтверждённая</option>
        </select>
      </div>
      <StaffTable path="/staff/accounts" nonce={nonce} params={{ q, status, trust }} columns={[
        { title: "Аккаунт", render: (a) => <a className="text-accent" href={`https://www.${a.platform}.com/@${a.handle}`} target="_blank" rel="noopener noreferrer nofollow">{a.platform} @{a.handle}</a> },
        { title: "Владелец", render: (a) => a.owner },
        { title: "Подписчики / среднее", render: (a) => `${a.followers != null ? formatCount(a.followers) : "—"} / ${a.avg_views != null ? formatCount(a.avg_views) : "—"}` },
        { title: "Статистика", render: (a) => a.trust_status ? <TrustBadge status={a.trust_status} /> : "—" },
        { title: "Статус", render: (a) => `${a.status}${a.is_listed ? " · в каталоге" : ""}` },
        { title: "Действия", render: (a) => (
          <span className="flex flex-wrap gap-2 text-xs">
            <button className="text-accent" onClick={() => act(a.id, "recheck")}>Перепроверить</button>
            <button className="text-accent" onClick={() => act(a.id, "review")}>На проверку</button>
            <button className="text-ok" onClick={() => act(a.id, "approve")}>Одобрить</button>
            <button className="text-muted" onClick={() => act(a.id, "hide")}>Скрыть</button>
            <button className="text-danger" onClick={() => act(a.id, "block")}>Блок</button>
          </span>) },
      ]} />
    </div>
  );
}
