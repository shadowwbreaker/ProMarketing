"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Avatar } from "@/components/profile/Avatar";
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

function UserMenu() {
  const { me, signOut } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);
  if (!me) return null;
  const item = "block px-4 py-2 text-sm hover:bg-bg";
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu"
        className="flex min-w-0 items-center gap-2 font-semibold hover:text-accent">
        <Avatar id={me.id} name={me.profile.display_name} size={28} src={me.profile.avatar_url} />
        <span className="hidden max-w-[9rem] truncate sm:inline">{me.profile.display_name}</span>
        <span className="text-xs">▾</span>
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-xl border border-border bg-surface py-1 shadow-lg" onClick={() => setOpen(false)}>
          <Link href={`/sellers/${me.id}`} className={item} role="menuitem">Мой профиль</Link>
          <Link href="/account/accounts/new" className={item} role="menuitem">+ Добавить аккаунт</Link>
          <Link href="/account?tab=purchases" className={item} role="menuitem">Мои покупки</Link>
          <Link href="/account?tab=accounts" className={item} role="menuitem">Мои аккаунты и продажи</Link>
          <Link href="/account?tab=messages" className={item} role="menuitem">Сообщения</Link>
          <Link href="/account?tab=profile" className={item} role="menuitem">Настройки</Link>
          <button className={`${item} w-full text-left text-danger`} role="menuitem"
            onClick={() => void signOut().then(() => router.replace("/"))}>Выйти</button>
        </div>
      )}
    </div>
  );
}

export function SiteHeader() {
  const { me, loading } = useAuth();
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="shrink-0 text-lg font-extrabold tracking-tight">
          Pro<span className="text-accent">Marketing</span>
        </Link>
        <nav className="flex min-w-0 items-center gap-3 text-sm sm:gap-4">
          <Link href="/catalog" className="hover:text-accent">Каталог</Link>
          <Link href="/support" className="hidden hover:text-accent sm:inline">Поддержка</Link>
          {loading ? null : me ? (
            <>
              {me.permissions.includes("staff.access") && <Link href="/staff" className="hover:text-accent" aria-label="Служебный раздел"><span className="sm:hidden">⚙</span><span className="hidden sm:inline">Служебный раздел</span></Link>}
              <Bell />
              <UserMenu />
            </>
          ) : (
            <>
              <Link href="/login" className="hover:text-accent">Войти</Link>
              <Link href="/register" className="hidden rounded-lg bg-accent px-3 py-1.5 font-semibold text-accent-ink sm:inline">Регистрация</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
