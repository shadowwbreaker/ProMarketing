import Link from "next/link";
import { LogoMark } from "@/components/Logo";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-muted">
        <span className="inline-flex items-center gap-2"><LogoMark size={20} /> YourVideoTeam · реклама в коротких видео</span>
        <nav aria-label="Нижнее меню" className="flex flex-wrap gap-x-5 gap-y-2">
          <Link href="/catalog" className="hover:text-text">Каталог</Link>
          <Link href="/terms" className="hover:text-text">Пользовательское соглашение</Link>
          <Link href="/rules" className="hover:text-text">Правила</Link>
          <Link href="/privacy" className="hover:text-text">Политика конфиденциальности</Link>
        </nav>
      </div>
    </footer>
  );
}
