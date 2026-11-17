"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { LoadingState } from "@/components/ui/States";
import { useAuth } from "@/lib/auth/AuthProvider";

export default function StaffLayout({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <LoadingState />;
  if (!me) return <Link className="font-semibold text-accent" href="/support/login">Вход для сотрудников</Link>;
  // Every staff endpoint also checks permissions on the backend.
  if (!me?.permissions.includes("staff.access")) return <p role="alert">Раздел доступен только сотрудникам.</p>;
  const p = new Set(me.permissions);
  return (
    <div className="flex flex-col gap-4">
      <nav className="flex flex-wrap gap-4 border-b border-border pb-2 text-sm font-semibold">
        <Link href="/staff">Обзор</Link>
        {p.has("support.work") && <Link href="/staff/tickets">Обращения</Link>}
        {p.has("arbitration.work") && <Link href="/staff/orders">Заказы</Link>}
        {(p.has("user.sanction") || p.has("staff.view_personal_data")) && <Link href="/staff/users">Пользователи</Link>}
        {p.has("moderation.stats") && <Link href="/staff/accounts">Каналы</Link>}
        {p.has("moderation.content") && <Link href="/staff/reviews">Модерация отзывов</Link>}
        {p.has("moderation.stats") && <Link href="/staff/fraud">Антифрод</Link>}
        {p.has("audit.view") && <Link href="/staff/audit">Журнал</Link>}
        {p.has("user.manage_roles") && <Link href="/staff/support/roles">Роли сотрудников</Link>}
      </nav>
      {children}
    </div>
  );
}
