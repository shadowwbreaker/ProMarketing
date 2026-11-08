"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { CardGrid, NetworkCard, OfferCard } from "@/components/catalog/Cards";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import type { Page } from "@/lib/api/auth";
import { getAdFormats } from "@/lib/api/catalog";
import { listCatalogNetworks, NetworkCard as NetT, OfferCard as OfferT, searchCatalog } from "@/lib/api/public";
import { fieldErrors } from "@/lib/forms";

const RUB_FIELDS = new Set(["price_min", "price_max"]);

function Filters({ params, onApply }: { params: URLSearchParams; onApply: (p: URLSearchParams) => void }) {
  const [formats, setFormats] = useState<{ value: string; label: string }[]>([]);
  useEffect(() => void getAdFormats().then(setFormats), []);
  const v = (k: string) => {
    const raw = params.get(k) ?? "";
    return RUB_FIELDS.has(k) && raw ? String(Number(raw) / 100) : raw;
  };

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const p = new URLSearchParams();
    new FormData(e.currentTarget).forEach((val, key) => {
      const s = String(val).trim();
      if (!s) return;
      p.set(key, RUB_FIELDS.has(key) ? String(Math.round(Number(s.replace(",", ".")) * 100)) : s);
    });
    onApply(p);
  }

  const input = "w-full rounded-lg border border-border bg-surface px-2 py-1.5 text-sm";
  return (
    <form onSubmit={submit} key={params.toString()} className="flex flex-col gap-3 text-sm" aria-label="Фильтры">
      <input name="q" defaultValue={v("q")} placeholder="Поиск" className={input} aria-label="Поиск" />
      <label>Тип
        <select name="kind" defaultValue={v("kind")} className={input}>
          <option value="">Отдельные аккаунты</option><option value="networks">Рекламные сетки</option>
        </select>
      </label>
      <label>Платформа
        <select name="platform" defaultValue={v("platform")} className={input}>
          <option value="">Все</option><option value="tiktok">TikTok</option><option value="youtube">YouTube Shorts</option>
        </select>
      </label>
      <fieldset className="grid grid-cols-2 gap-2"><legend>Подписчики</legend>
        <input name="followers_min" type="number" min={0} defaultValue={v("followers_min")} placeholder="от" className={input} aria-label="Подписчики от" />
        <input name="followers_max" type="number" min={0} defaultValue={v("followers_max")} placeholder="до" className={input} aria-label="Подписчики до" />
      </fieldset>
      <fieldset className="grid grid-cols-2 gap-2"><legend>Цена, ₽</legend>
        <input name="price_min" inputMode="decimal" defaultValue={v("price_min")} placeholder="от" className={input} aria-label="Цена от" />
        <input name="price_max" inputMode="decimal" defaultValue={v("price_max")} placeholder="до" className={input} aria-label="Цена до" />
      </fieldset>
      <details className="rounded-lg border border-border p-2" open={["avg_min", "avg_max", "category", "language", "geo", "ad_format", "rating_min"].some((k) => !!v(k))}>
        <summary className="cursor-pointer select-none font-medium">Ещё фильтры</summary>
        <div className="mt-3 flex flex-col gap-3">
        <fieldset className="grid grid-cols-2 gap-2"><legend>Средние просмотры</legend>
          <input name="avg_min" type="number" min={0} defaultValue={v("avg_min")} placeholder="от" className={input} aria-label="Просмотры от" />
          <input name="avg_max" type="number" min={0} defaultValue={v("avg_max")} placeholder="до" className={input} aria-label="Просмотры до" />
        </fieldset>
        <label>Категория<input name="category" defaultValue={v("category")} className={input} /></label>
        <label>Язык<input name="language" defaultValue={v("language")} placeholder="ru" className={input} /></label>
        <label>География<input name="geo" defaultValue={v("geo")} className={input} /></label>
        <label>Формат рекламы
          <select name="ad_format" defaultValue={v("ad_format")} className={input}>
            <option value="">Любой</option>
            {formats.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </label>
        <label>Рейтинг продавца от<input name="rating_min" type="number" min={1} max={5} step={0.5} defaultValue={v("rating_min")} className={input} /></label>
        </div>
      </details>
      <label className="flex items-center gap-2"><input type="checkbox" name="verified" value="1" defaultChecked={v("verified") === "1"} /> Только подтверждённая статистика</label>
      <label>Сортировка
        <select name="sort" defaultValue={v("sort")} className={input}>
          <option value="">Новые</option><option value="popular">Популярные</option><option value="price_asc">Дешевле</option>
          <option value="price_desc">Дороже</option><option value="followers">Больше подписчиков</option><option value="views">Больше просмотров</option>
        </select>
      </label>
      <button className="rounded-lg bg-accent px-4 py-2 font-semibold text-accent-ink">Применить</button>
    </form>
  );
}

function CatalogInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const qs = params.toString();
  const isNetworks = params.get("kind") === "networks";
  const [state, setState] = useState<{ loading: boolean; offers?: Page<OfferT>; nets?: Page<NetT>; error?: string }>({ loading: true });

  useEffect(() => {
    let alive = true;
    setState({ loading: true });
    const p = new URLSearchParams(qs);
    p.delete("kind");
    const req = isNetworks
      ? listCatalogNetworks(p.toString()).then((nets) => ({ loading: false, nets }))
      : searchCatalog(p.toString()).then((offers) => ({ loading: false, offers }));
    req.then((s) => alive && setState(s)).catch((e) => alive && setState({ loading: false, error: fieldErrors(e).form }));
    return () => {
      alive = false;
    };
  }, [qs, isNetworks]);

  const count = state.offers?.count ?? state.nets?.count ?? 0;
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-[240px_1fr] [&>*]:min-w-0">
      <aside><Filters params={params} onApply={(p) => router.push(`${pathname}?${p.toString()}`)} /></aside>
      <section>
        <h1 className="mb-4 text-2xl font-bold">{isNetworks ? "Рекламные сетки" : "Каталог"} {!state.loading && <span className="text-base font-normal text-muted">{count}</span>}</h1>
        {state.loading && <LoadingState />}
        {state.error && <ErrorState message={state.error} />}
        {!state.loading && !state.error && count === 0 && <EmptyState title="Ничего не найдено">Попробуйте ослабить фильтры.</EmptyState>}
        <CardGrid>
          {state.offers?.results.map((o) => <OfferCard key={o.id} o={o} />)}
          {state.nets?.results.map((n) => <NetworkCard key={n.id} n={n} />)}
        </CardGrid>
      </section>
    </div>
  );
}

export default function CatalogPage() {
  return <Suspense><CatalogInner /></Suspense>;
}
