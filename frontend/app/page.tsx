"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { OfferTable } from "@/components/catalog/OfferTable";
import { ShortsFan } from "@/components/ShortsFan";
import { getCatalogCounts, getHome, OfferCard } from "@/lib/api/public";

const STEPS = [
  ["Выберите канал", "Подписчики и просмотры получены из TikTok и YouTube, а не со слов продавца."],
  ["Оплатите заказ", "Деньги удерживает платёжный провайдер — продавец их пока не получает."],
  ["Проверьте ролик", "Продавец публикует рекламу и присылает ссылку. Вы подтверждаете или открываете спор."],
  ["Выплата продавцу", "Через 48 часов после подтверждения. Спор приостанавливает выплату."],
];

/** Home: what the platform is, how a deal works, where to go next. Nothing else. */
export default function HomePage() {
  const [popular, setPopular] = useState<OfferCard[]>();
  const [total, setTotal] = useState<number>();
  useEffect(() => {
    getHome().then((h) => setPopular(h.popular.slice(0, 5))).catch(() => setPopular([]));
    getCatalogCounts().then((c) => setTotal(c.accounts)).catch(() => {});
  }, []);

  return (
    <div className="flex flex-col gap-16 sm:gap-20">
      <section className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="stagger">
          <p className="inline-flex items-center gap-2 rounded-full bg-bg px-3 py-1 text-xs font-semibold text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />Маркетплейс рекламы в коротких видео
          </p>
          <h1 className="mt-4 text-4xl font-extrabold leading-[1.05] tracking-tight text-balance sm:text-5xl lg:text-6xl">
            Реклама у авторов TikTok и YouTube&nbsp;Shorts —{" "}
            <span className="bg-gradient-to-r from-accent to-[#7c4dff] bg-clip-text text-transparent">оплата после проверки</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
            Находите каналы с настоящей статистикой и платите безопасно: продавец получит деньги, только когда вы подтвердите выполнение.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/catalog" className="rounded-xl bg-accent px-6 py-3 font-semibold text-accent-ink shadow-[0_8px_20px_-8px_rgb(255_61_90/0.7)] transition-[translate,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_12px_24px_-8px_rgb(255_61_90/0.75)] motion-reduce:hover:translate-y-0">
              Найти канал{total ? ` · ${total}` : ""}
            </Link>
            <Link href="/account/accounts/new" className="rounded-xl border border-border px-6 py-3 font-semibold transition-colors duration-150 hover:border-text">
              Продать рекламу
            </Link>
          </div>
          <p className="mt-5 text-sm text-muted">Комиссия 5% · выплата через 48 часов после подтверждения · споры решает поддержка</p>
        </div>
        <ShortsFan className="mx-auto w-full max-w-sm lg:max-w-none" />
      </section>

      <section aria-labelledby="how">
        <h2 id="how" className="text-2xl font-extrabold tracking-tight sm:text-3xl">Как проходит сделка</h2>
        <ol className="rows mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(([t, d], i) => (
            <li key={t} className="rounded-2xl border border-border p-5 transition-[border-color,translate] duration-200 ease-out hover:-translate-y-0.5 hover:border-accent/40 motion-reduce:hover:translate-y-0">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-[30%] bg-gradient-to-br from-accent to-[#7c4dff] text-sm font-extrabold text-white">{i + 1}</span>
              <p className="mt-3 font-bold">{t}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted">{d}</p>
            </li>
          ))}
        </ol>
      </section>

      {popular && popular.length > 0 && (
        <section aria-labelledby="popular">
          <div className="mb-4 flex items-baseline justify-between gap-3">
            <h2 id="popular" className="text-2xl font-extrabold tracking-tight sm:text-3xl">Популярные каналы</h2>
            <Link href="/catalog" className="text-sm font-semibold text-accent hover:underline">Весь каталог →</Link>
          </div>
          <OfferTable offers={popular} />
        </section>
      )}

      <section className="relative overflow-hidden rounded-3xl bg-text px-6 py-10 text-surface sm:px-10">
        <div aria-hidden className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-gradient-to-br from-accent to-[#7c4dff] opacity-60 blur-3xl" />
        <div className="relative max-w-xl">
          <h2 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Ведёте канал в TikTok или YouTube Shorts?</h2>
          <p className="mt-2 text-surface/75">Добавьте канал за пару минут: укажите ссылку — статистика подтянется сама — и опишите условия рекламы.</p>
          <Link href="/account/accounts/new" className="mt-6 inline-block rounded-xl bg-surface px-6 py-3 font-semibold text-text transition-[translate] duration-200 ease-out hover:-translate-y-0.5 motion-reduce:hover:translate-y-0">
            Добавить канал
          </Link>
        </div>
      </section>
    </div>
  );
}
