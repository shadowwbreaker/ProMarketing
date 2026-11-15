"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Logo } from "@/components/Logo";
import { Avatar } from "@/components/profile/Avatar";
import { inboxStatus } from "@/lib/api/chat";
import { useAuth } from "@/lib/auth/AuthProvider";
import { useInboxSound } from "@/lib/useInboxSound";
import { useLivePolling } from "@/lib/useLivePolling";

function UserMenu({ sound, toggleSound }: { sound: boolean; toggleSound: () => void }) {
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
  const item = "block px-4 py-2 text-sm transition-colors duration-150 hover:bg-bg";
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu"
        className="flex min-w-0 items-center gap-2 font-semibold hover:text-accent">
        <Avatar id={me.id} name={me.profile.display_name} size={28} src={me.profile.avatar_url} />
        <span className="hidden max-w-[9rem] truncate sm:inline">{me.profile.display_name}</span>
        <span className="hidden text-xs sm:inline">▾</span>
      </button>
      {open && (
        <div role="menu" className="pop absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-2xl border border-border bg-surface py-1.5 shadow-xl" onClick={() => setOpen(false)}>
          <Link href={`/sellers/${me.id}`} className={item} role="menuitem">Мой профиль</Link>
          <Link href="/account/accounts/new" className={item} role="menuitem">+ Добавить канал</Link>
          <Link href="/purchases" className={`${item} md:hidden`} role="menuitem">Мои покупки</Link>
          <Link href="/account?tab=accounts" className={item} role="menuitem">Мои каналы</Link>
          <Link href="/favorites" className={`${item} sm:hidden`} role="menuitem">Избранное</Link>
          {me.permissions.includes("staff.access") && <Link href="/staff" className={`${item} lg:hidden`} role="menuitem">Служебный раздел</Link>}
          <Link href="/support" className={item} role="menuitem">Помощь</Link>
          <Link href="/account?tab=profile" className={item} role="menuitem">Настройки</Link>
          <button type="button" role="menuitemcheckbox" aria-checked={sound} className={`${item} w-full text-left`} onClick={toggleSound}>
            Звук сообщений: {sound ? "вкл." : "выкл."}
          </button>
          <button className={`${item} w-full text-left text-danger`} role="menuitem"
            onClick={() => void signOut().then(() => router.replace("/"))}>Выйти</button>
        </div>
      )}
    </div>
  );
}

function OrderNavigation({ sound, announce }: { sound: boolean; announce: ReturnType<typeof useInboxSound>["announce"] }) {
  const [status, setStatus] = useState({ unread: false, has_received_orders: false });
  const path = usePathname();
  const load = useCallback(async () => {
    try {
      const result = await inboxStatus();
      setStatus(result);
      announce(result.signals);
    } catch { /* The next refresh retries the inbox. */ }
  }, [announce]);
  useLivePolling(load, path === "/messages" || path.startsWith("/orders") ? 2500 : 5000, "inbox-updated", sound);
  return (
    <>
      {status.has_received_orders && <NavLink href="/orders">Заказы</NavLink>}
      <NavLink href="/messages" className="relative">
        Сообщения
        {status.unread && (
          <span className="page-enter absolute right-0.5 top-0 h-2 w-2 rounded-full bg-[#e5243b] ring-2 ring-surface">
            <span className="sr-only">Есть непрочитанные</span>
          </span>
        )}
      </NavLink>
    </>
  );
}

function NavLink({ href, children, className = "" }: { href: string; children: React.ReactNode; className?: string }) {
  const path = usePathname();
  const on = path === href || path.startsWith(`${href}/`);
  return (
    <Link href={href} aria-current={on ? "page" : undefined}
      className={`whitespace-nowrap rounded-lg px-2 py-1 font-semibold transition-colors duration-150 ${on ? "bg-bg text-text" : "text-muted hover:text-text"} ${className}`}>
      {children}
    </Link>
  );
}

export function SiteHeader() {
  const { me, loading } = useAuth();
  const sound = useInboxSound(me?.id ?? "");
  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-surface/85 backdrop-blur-md supports-[backdrop-filter]:bg-surface/75">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="shrink-0" aria-label="YourVideoTeam — на главную"><Logo /></Link>
        <nav className="flex min-w-0 items-center gap-1 text-sm sm:gap-2" aria-label="Основное меню">
          <NavLink href="/catalog">Каталог</NavLink>
          {loading ? null : me ? (
            <>
              <NavLink href="/purchases" className="hidden md:inline">Покупки</NavLink>
              <OrderNavigation key={me.id} sound={sound.enabled} announce={sound.announce} />
              <NavLink href="/favorites" className="hidden sm:inline">Избранное</NavLink>
              {me.permissions.includes("staff.access") && <NavLink href="/staff" className="hidden lg:inline">Служебный раздел</NavLink>}
              <UserMenu sound={sound.enabled} toggleSound={sound.toggle} />
            </>
          ) : (
            <>
              <NavLink href="/support" className="hidden sm:inline">Помощь</NavLink>
              <NavLink href="/login">Войти</NavLink>
              <Link href="/register" className="hidden rounded-lg bg-accent px-3 py-1.5 font-semibold text-accent-ink sm:inline">Регистрация</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
