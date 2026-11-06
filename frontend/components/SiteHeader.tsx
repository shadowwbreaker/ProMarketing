"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { unreadCount } from "@/lib/api/chat";
import { useAuth } from "@/lib/auth/AuthProvider";

function Bell() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const load = () => unreadCount().then((r) => setN(r.unread)).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);
  return (
    <Link href="/account?tab=notifications" aria-label={`Уведомления: ${n}`} className="relative hover:text-accent">
      🔔{n > 0 && <span className="absolute -right-2 -top-1 rounded-full bg-accent px-1 text-[10px] font-bold text-accent-ink">{n > 99 ? "99+" : n}</span>}
    </Link>
  );
}

export function SiteHeader() {
  const { me, loading } = useAuth();
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="text-lg font-extrabold tracking-tight">
          Pro<span className="text-accent">Marketing</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/catalog" className="hover:text-accent">Каталог</Link>
          {loading ? null : me ? (
            <>
              <Bell />
              <Link href="/account" className="font-semibold hover:text-accent">{me.profile.display_name}</Link>
            </>
          ) : (
            <Link href="/login" className="hover:text-accent">Войти</Link>
          )}
        </nav>
      </div>
    </header>
  );
}
