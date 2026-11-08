"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { CardGrid, NetworkCard, OfferCard } from "@/components/catalog/Cards";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import type { Page } from "@/lib/api/auth";
import { getAdFormats } from "@/lib/api/catalog";
import { listCatalogNetworks, NetworkCard as NetT, OfferCard as OfferT, searchCatalog } from "@/lib/api/public";
import { fieldErrors } from "@/lib/forms";

const RUB_FIELDS = new Set(["price_min", "price_max"]);
/** Keys controlled outside the filter sheet (search box, sort, accounts/networks tabs). */
const OUTSIDE = new Set(["q", "sort", "kind", "page"]);

const input = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm";

function FilterSheet({ open, params, onApply, onClose }: {
  open: boolean;
  params: URLSearchParams;
  onApply: (p: URLSearchParams) => void;
  onClose: () => void;
}) {
  const [formats, setFormats] = useState<{ value: string; label: string }[]>([]);
  const first = useRef<HTMLSelectElement>(null);
  useEffect(() => void getAdFormats().then(setFormats).catch(() => {}), []);
  useEffect(() => {
    if (!open) return;
    first.current?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const v = (k: string) => {
    const raw = params.get(k) ?? "";
    return RUB_FIELDS.has(k) && raw ? String(Number(raw) / 100) : raw;
  };

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const p = new URLSearchParams();
    OUTSIDE.forEach((k) => k !== "page" && params.get(k) && p.set(k, params.get(k)!));
    new FormData(e.currentTarget).forEach((val, key) => {
      const s = String(val).trim();
      if (!s) return;
      p.set(key, RUB_FIELDS.has(key) ? String(Math.round(Number(s.replace(",", ".")) * 100)) : s);
    });
    onApply(p);
  }

  function reset() {
    const p = new URLSearchParams();
    OUTSIDE.forEach((k) => k !== "page" && params.get(k) && p.set(k, params.get(k)!));
    onApply(p);
  }

  return (
    <>
      {/* backdrop */}
      <div
        aria-hidden
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/30 transition-opacity duration-200 ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
      />
      {/* top sheet: slides down from the top edge, slides back up on apply/close; opacity-only under reduced motion */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Фильтры каталога"
        inert={!open}
        className={`fixed inset-x-0 top-0 z-50 max-h-[85dvh] overflow-y-auto overscroll-contain rounded-b-2xl bg-surface shadow-xl
          transition-[translate,opacity,visibility] ease-[cubic-bezier(0.2,0,0,1)] motion-reduce:translate-y-0
          ${open ? "visible translate-y-0 opacity-100 duration-300" : "invisible -translate-y-full opacity-0 duration-200"}`}
      >
        <form onSubmit={submit} key={params.toString()} className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-5 text-sm" aria-label="Фильтры">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">Фильтры</h2>
            <button type="button" onClick={onClose} aria-label="Закрыть фильтры" className="rounded-lg px-2 py-1 text-xl leading-none text-muted hover:text-text">×</button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="flex flex-col gap-1">Платформа
              <select ref={first} name="platform" defaultValue={v("platform")} className={input}>
                <option value="">Все</option><option value="tiktok">TikTok</option><option value="youtube">YouTube Shorts</option>
              </select>
            </label>
            <fieldset className="flex flex-col gap-1"><legend className="mb-1">Подписчики</legend>
              <div className="grid grid-cols-2 gap-2">
                <input name="followers_min" type="number" min={0} defaultValue={v("followers_min")} placeholder="от" className={input} aria-label="Подписчики от" />
                <input name="followers_max" type="number" min={0} defaultValue={v("followers_max")} placeholder="до" className={input} aria-label="Подписчики до" />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1"><legend className="mb-1">Цена, ₽</legend>
              <div className="grid grid-cols-2 gap-2">
                <input name="price_min" inputMode="decimal" defaultValue={v("price_min")} placeholder="от" className={input} aria-label="Цена от" />
                <input name="price_max" inputMode="decimal" defaultValue={v("price_max")} placeholder="до" className={input} aria-label="Цена до" />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1"><legend className="mb-1">Просмотры на видео</legend>
              <div className="grid grid-cols-2 gap-2">
                <input name="avg_min" type="number" min={0} defaultValue={v("avg_min")} placeholder="от" className={input} aria-label="Просмотры от" />
                <input name="avg_max" type="number" min={0} defaultValue={v("avg_max")} placeholder="до" className={input} aria-label="Просмотры до" />
              </div>
            </fieldset>
            <label className="flex flex-col gap-1">Формат рекламы
              <select name="ad_format" defaultValue={v("ad_format")} className={input}>
                <option value="">Любой</option>
                {formats.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">Категория<input name="category" defaultValue={v("category")} placeholder="например, юмор" className={input} /></label>
            <label className="flex flex-col gap-1">География<input name="geo" defaultValue={v("geo")} placeholder="Россия" className={input} /></label>
            <label className="flex flex-col gap-1">Язык<input name="language" defaultValue={v("language")} placeholder="ru" className={input} /></label>
            <label className="flex flex-col gap-1">Рейтинг продавца от<input name="rating_min" type="number" min={1} max={5} step={0.5} defaultValue={v("rating_min")} className={input} /></label>
          </div>
          <label className="flex items-center gap-2"><input type="checkbox" name="verified" value="1" defaultChecked={v("verified") === "1"} /> Только данные, подтверждённые платформой</label>
          <div className="sticky bottom-0 -mx-4 -mb-5 flex gap-2 border-t border-border bg-surface px-4 py-4">
            <button type="button" onClick={reset} className="rounded-lg border border-border px-4 py-2 font-semibold">Сбросить</button>
            <button className="flex-1 rounded-lg bg-accent px-4 py-2 font-semibold text-accent-ink">Применить</button>
          </div>
        </form>
      </div>
    </>
  );
}

function CatalogInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const qs = params.toString();
  const isNetworks = params.get("kind") === "networks";
  const [open, setOpen] = useState(false);
  const filtersBtn = useRef<HTMLButtonElement>(null);
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

  const go = (p: URLSearchParams) => router.push(`${pathname}${p.toString() ? `?${p}` : ""}`, { scroll: false });
  const setParam = (k: string, val: string) => {
    const p = new URLSearchParams(qs);
    if (val) p.set(k, val);
    else p.delete(k);
    p.delete("page");
    go(p);
  };
  const close = () => {
    setOpen(false);
    filtersBtn.current?.focus({ preventScroll: true });
  };
  const active = [...params.keys()].filter((k) => !OUTSIDE.has(k)).length;
  const count = state.offers?.count ?? state.nets?.count ?? 0;
  const tab = (on: boolean) => `rounded-lg px-3 py-1.5 font-semibold ${on ? "bg-surface shadow-sm" : "text-muted hover:text-text"}`;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-2xl font-bold">
          {isNetworks ? "Рекламные сетки" : "Каталог"} {!state.loading && <span className="text-base font-normal text-muted">{count}</span>}
        </h1>
        <nav aria-label="Что показывать" className="flex rounded-xl bg-bg p-1 text-sm">
          <Link href="/catalog" className={tab(!isNetworks)} aria-current={!isNetworks ? "page" : undefined}>Аккаунты</Link>
          <Link href="/catalog?kind=networks" className={tab(isNetworks)} aria-current={isNetworks ? "page" : undefined}>Сетки</Link>
        </nav>
      </div>

      <div className="flex flex-wrap gap-2 text-sm">
        <form
          key={params.get("q") ?? ""}
          onSubmit={(e) => {
            e.preventDefault();
            setParam("q", String(new FormData(e.currentTarget).get("q") ?? "").trim());
          }}
          className="flex min-w-0 flex-[1_1_16rem] gap-2"
        >
          <input name="q" defaultValue={params.get("q") ?? ""} placeholder="Тематика, название, @аккаунт" aria-label="Поиск по каталогу" className={`${input} min-w-0`} />
          <button className="shrink-0 rounded-lg bg-text px-4 py-2 font-semibold text-surface">Найти</button>
        </form>
        <select aria-label="Сортировка" value={params.get("sort") ?? ""} onChange={(e) => setParam("sort", e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm">
          <option value="">Сначала новые</option><option value="popular">Популярные</option><option value="price_asc">Дешевле</option>
          <option value="price_desc">Дороже</option><option value="followers">Больше подписчиков</option><option value="views">Больше просмотров</option>
        </select>
        <button
          ref={filtersBtn}
          type="button"
          onClick={() => setOpen(true)}
          aria-expanded={open}
          aria-haspopup="dialog"
          className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2 font-semibold hover:border-accent"
        >
          <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h16M7 12h10M10 18h4" /></svg>
          Фильтры
          {active > 0 && <span className="rounded-full bg-accent px-1.5 text-xs text-accent-ink">{active}</span>}
        </button>
      </div>

      <FilterSheet
        open={open}
        params={params}
        onClose={close}
        onApply={(p) => {
          close();
          go(p);
        }}
      />

      {state.loading && <LoadingState />}
      {state.error && <ErrorState message={state.error} />}
      {!state.loading && !state.error && count === 0 && <EmptyState title="Ничего не найдено">Попробуйте ослабить фильтры.</EmptyState>}
      <CardGrid>
        {state.offers?.results.map((o) => <OfferCard key={o.id} o={o} />)}
        {state.nets?.results.map((n) => <NetworkCard key={n.id} n={n} />)}
      </CardGrid>
    </div>
  );
}

export default function CatalogPage() {
  return <Suspense><CatalogInner /></Suspense>;
}
