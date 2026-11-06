"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { CardGrid, NetworkCard, OfferCard } from "@/components/catalog/Cards";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { getHome, Home } from "@/lib/api/public";
import { fieldErrors } from "@/lib/forms";

function Block({ title, href, children }: { title: string; href?: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-xl font-bold">{title}</h2>
        {href && <Link href={href} className="text-sm text-accent">Смотреть все</Link>}
      </div>
      {children}
    </section>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [home, setHome] = useState<Home>();
  const [err, setErr] = useState<string>();

  useEffect(() => {
    getHome().then(setHome).catch((e) => setErr(fieldErrors(e).form));
  }, []);

  function search(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = String(new FormData(e.currentTarget).get("q") ?? "").trim();
    router.push(q ? `/catalog?q=${encodeURIComponent(q)}` : "/catalog");
  }

  return (
    <>
      <section className="grid grid-cols-1 gap-8 py-6 md:grid-cols-[1.4fr_1fr] md:items-center [&>*]:min-w-0">
        <div>
          <h1 className="text-3xl font-extrabold leading-tight tracking-tight break-words sm:text-4xl md:text-5xl">
            Реклама у авторов коротких видео — <span className="text-accent">с защитой сделки</span>
          </h1>
          <p className="mt-4 max-w-xl text-muted">
            Аккаунты TikTok и YouTube Shorts с реальной статистикой. Оплата удерживается у платёжного провайдера и
            переводится продавцу через 48 часов после того, как вы подтвердите выполнение.
          </p>
          <form onSubmit={search} role="search" className="mt-6 flex max-w-xl gap-2">
            <input
              name="q"
              aria-label="Поиск по каталогу"
              placeholder="Тематика, название, @аккаунт"
              className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-4 py-3 outline-none focus:ring-2 focus:ring-accent"
            />
            <button className="rounded-lg bg-accent px-5 py-3 font-semibold text-accent-ink">Найти</button>
          </form>
        </div>
        <ul className="grid gap-3 text-sm">
          {[
            ["Статистика по запросу", "Средние просмотры последних 15 видео из официальных API, с датой обновления"],
            ["Защита сделки", "Деньги у провайдера до выполнения; при споре выплата приостанавливается"],
            ["Арбитраж", "Жалобы рассматривает администрация по фактам и доказательствам обеих сторон"],
          ].map(([t, d]) => (
            <li key={t} className="rounded-xl border border-border bg-surface p-4">
              <p className="font-semibold">{t}</p>
              <p className="mt-1 text-muted">{d}</p>
            </li>
          ))}
        </ul>
      </section>

      {err && <ErrorState message={err} />}
      {!home && !err && <LoadingState />}
      {home && (
        <>
          {home.categories.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-2">
              {home.categories.map((c) => (
                <Link key={c.category} href={`/catalog?category=${encodeURIComponent(c.category)}`}
                  className="rounded-full border border-border bg-surface px-3 py-1 text-sm hover:border-accent">
                  {c.category} <span className="text-muted">{c.count}</span>
                </Link>
              ))}
            </div>
          )}
          {home.popular.length > 0 && <Block title="Популярные предложения" href="/catalog?sort=popular"><CardGrid>{home.popular.map((o) => <OfferCard key={o.id} o={o} />)}</CardGrid></Block>}
          {home.recommended.length > 0 && <Block title="Рекомендуем: подтверждённая статистика" href="/catalog?verified=1&sort=views"><CardGrid>{home.recommended.map((o) => <OfferCard key={o.id} o={o} />)}</CardGrid></Block>}
          {home.new.length > 0 && <Block title="Новые" href="/catalog?sort=new"><CardGrid>{home.new.map((o) => <OfferCard key={o.id} o={o} />)}</CardGrid></Block>}
          {home.networks.length > 0 && <Block title="Рекламные сетки" href="/catalog?kind=networks"><CardGrid>{home.networks.map((n) => <NetworkCard key={n.id} n={n} />)}</CardGrid></Block>}
          {!home.popular.length && !home.networks.length && (
            <p className="mt-10 text-center text-muted">Каталог пока пуст. <Link href="/register" className="text-accent">Станьте первым продавцом</Link>.</p>
          )}
        </>
      )}
    </>
  );
}
