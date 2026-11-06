"use client";

import { useEffect, useState } from "react";
import { SearchBar, StaffTable } from "@/components/StaffTable";
import { apiFetch } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";

export default function StaffAudit() {
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [staffOnly, setStaffOnly] = useState("1");
  const [chain, setChain] = useState<{ ok: boolean; entries: number }>();
  useEffect(() => void apiFetch<{ ok: boolean; entries: number }>("/staff/audit/verify").then(setChain).catch(() => {}), []);
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Журнал действий</h1>
      {chain && <p className={`text-sm ${chain.ok ? "text-ok" : "text-danger"}`}>Целостность журнала: {chain.ok ? "не нарушена" : "НАРУШЕНА"} · записей {chain.entries}</p>}
      <div className="flex flex-wrap gap-2">
        <SearchBar value={action} onChange={setAction} placeholder="Действие (начало), Enter" />
        <SearchBar value={actor} onChange={setActor} placeholder="Email сотрудника, Enter" />
        <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={staffOnly === "1"} onChange={(e) => setStaffOnly(e.target.checked ? "1" : "")} /> только сотрудники</label>
      </div>
      <StaffTable path="/staff/audit" params={{ action, actor, staff: staffOnly }} columns={[
        { title: "Время", render: (e) => formatDateTime(e.created_at) },
        { title: "Кто", render: (e) => e.actor },
        { title: "Действие", render: (e) => e.action },
        { title: "Объект", render: (e) => `${e.subject_type} ${String(e.subject_id).slice(0, 8)}` },
        { title: "Было → стало", render: (e) => <span className="text-xs">{JSON.stringify(e.before)} → {JSON.stringify(e.after)}</span> },
        { title: "Причина / комментарий", render: (e) => [e.reason, e.comment].filter(Boolean).join(" · ") },
      ]} />
    </div>
  );
}
