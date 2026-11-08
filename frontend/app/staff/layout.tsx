"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { LoadingState } from "@/components/ui/States";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function StaffLayout({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <LoadingState />;
  // UI guard only — every staff endpoint checks permissions on the backend.
  if (!me?.permissions.includes("staff.access")) return <p role="alert">Раздел доступен только сотрудникам.</p>;
  const p = new Set(me.permissions);
  return (
    <div className="flex flex-col gap-4">
      <nav className="flex flex-wrap gap-4 border-b border-border pb-2 text-sm font-semibold">
        <Link href="/staff">Обзор</Link>
        {p.has("dispute.handle") && <Link href="/staff/disputes">Споры</Link>}
        <Link href="/staff/tickets">Обращения</Link>
        {p.has("staff.view_orders") && <Link href="/staff/orders">Заказы</Link>}
        {(p.has("user.sanction") || p.has("staff.view_personal_data")) && <Link href="/staff/users">Пользователи</Link>}
        {p.has("moderation.stats") && <Link href="/staff/accounts">Каналы</Link>}
        {p.has("moderation.content") && <Link href="/staff/reviews">Отзывы</Link>}
        {p.has("moderation.stats") && <Link href="/staff/fraud">Антифрод</Link>}
        <Link href="/staff/audit">Журнал</Link>
      </nav>
      {children}
    </div>
  );
}
