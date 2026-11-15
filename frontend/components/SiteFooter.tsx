import Link from "next/link";
import { LogoMark } from "@/components/Logo";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-muted">
        <span className="inline-flex items-center gap-2"><LogoMark size={20} /> YourVideoTeam · реклама в коротких видео</span>
        <nav aria-label="Нижнее меню" className="flex flex-wrap gap-x-5 gap-y-2">
          <Link href="/catalog" className="hover:text-text">Каталог</Link>
          <Link href="/support" className="hover:text-text">Помощь</Link>
          <Link href="/rules" className="hover:text-text">Правила</Link>
          <Link href="/guide" className="hover:text-text">Документация</Link>
        </nav>
        <nav aria-label="Документы сервиса" className="flex w-full flex-wrap gap-2">
          <Link href="/terms" className="inline-flex min-h-10 items-center rounded-lg border border-border px-3 py-2 font-semibold text-text hover:bg-bg">Пользовательское соглашение</Link>
          <Link href="/privacy" className="inline-flex min-h-10 items-center rounded-lg border border-border px-3 py-2 font-semibold text-text hover:bg-bg">Политика конфиденциальности</Link>
        </nav>
      </div>
    </footer>
  );
}
