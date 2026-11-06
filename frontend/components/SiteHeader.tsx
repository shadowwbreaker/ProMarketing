"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth/AuthProvider";

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
            <Link href="/account" className="font-semibold hover:text-accent">{me.profile.display_name}</Link>
          ) : (
            <Link href="/login" className="hover:text-accent">Войти</Link>
          )}
        </nav>
      </div>
    </header>
  );
}
