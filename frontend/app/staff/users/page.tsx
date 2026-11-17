"use client";

import Link from "next/link";
import { useState } from "react";
import { SearchBar, StaffTable } from "@/components/StaffTable";
import { formatDateTime } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/roles";

export default function StaffUsers() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Пользователи</h1>
      <div className="flex flex-wrap gap-2">
        <SearchBar value={q} onChange={setQ} placeholder="Email или имя, Enter" />
        <select aria-label="Статус" value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-border bg-surface px-2 text-sm">
          <option value="">Все</option><option value="active">Активные</option><option value="limited">Ограничены</option><option value="blocked">Заблокированы</option>
        </select>
      </div>
      <StaffTable path="/staff/users" params={{ q, status }} columns={[
        { title: "Email", render: (u) => <Link className="text-accent" href={`/staff/users/${u.id}`}>{u.email}</Link> },
        { title: "Имя", render: (u) => u.display_name },
        { title: "Роли", render: (u) => u.roles.map((role: string) => ROLE_LABELS[role] ?? role).join(", ") },
        { title: "Статус", render: (u) => u.status },
        { title: "Регистрация", render: (u) => formatDateTime(u.date_joined) },
      ]} />
    </div>
  );
}
