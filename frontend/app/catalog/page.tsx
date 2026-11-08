"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { OfferTable } from "@/components/catalog/OfferTable";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import type { Page } from "@/lib/api/auth";
import { getAdFormats } from "@/lib/api/catalog";
import { getCatalogCounts, listCatalogNetworks, NetworkCard as NetT, OfferCard as OfferT, searchCatalog } from "@/lib/api/public";
import { fieldErrors } from "@/lib/forms";

const RUB_FIELDS = new Set(["price_min", "price_max"]);
/** Keys controlled outside the filter sheet (search box, sort, accounts/networks tabs). */
const OUTSIDE = new Set(["q", "sort", "kind", "page", "online", "verified"]);

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
          <div className="sticky bottom-0 -mx-4 -mb-5 flex gap-2 border-t border-border bg-surface px-4 py-4">
            <button type="button" onClick={reset} className="rounded-lg border border-border px-4 py-2 font-semibold">Сбросить</button>
            <button className="flex-1 rounded-lg bg-accent px-4 py-2 font-semibold text-accent-ink">Применить</button>
          </div>
        </form>
      </div>
    </>
  );
}

function Toggle({ label, on, onChange }: { label: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm font-semibold">
      {label}
      <input type="checkbox" role="switch" checked={on} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span aria-hidden className="relative h-5 w-9 rounded-full bg-border transition-colors duration-150 peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent
        after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-surface after:shadow after:transition-[translate] after:duration-150 peer-checked:after:translate-x-4" />
    </label>
  );
}

type Counts = { accounts: number; tiktok: number; youtube: number; networks: number };

/** Category bubbles as on FunPay: the bigger the section, the bigger the circle. */
function Bubbles({ counts, active }: { counts?: Counts; active: string }) {
  const items: { key: string; label: string; href: string; n?: number }[] = [
    { key: "all", label: "Все каналы", href: "/catalog", n: counts?.accounts },
    { key: "tiktok", label: "TikTok", href: "/catalog?platform=tiktok", n: counts?.tiktok },
    { key: "youtube", label: "YouTube Shorts", href: "/catalog?platform=youtube", n: counts?.youtube },
    { key: "networks", label: "Сетки", href: "/catalog?kind=networks", n: counts?.networks },
  ];
  const max = Math.max(1, ...items.map((i) => i.n ?? 0));
  return (
    <nav aria-label="Разделы каталога" className="flex flex-wrap items-center gap-2 sm:gap-5">
      {items.map((i) => {
        const on = i.key === active;
        const size = 84 + Math.round(40 * Math.sqrt((i.n ?? 0) / max));
        return (
          <Link key={i.key} href={i.href} aria-current={on ? "page" : undefined}
            style={{ "--s": `${Math.round(size * 0.7)}px`, "--l": `${size}px` } as React.CSSProperties}
            className={`flex h-[var(--s)] w-[var(--s)] shrink-0 flex-col sm:h-[var(--l)] sm:w-[var(--l)] items-center justify-center rounded-full text-center text-sm font-bold transition-colors duration-150
              ${on ? "bg-text text-surface" : "bg-bg text-accent hover:bg-border"}`}>
            <span className="px-2 text-xs leading-tight sm:text-sm">{i.label}</span>
            <span className={`mt-1 text-xs font-medium ${on ? "text-surface/80" : "text-muted"}`}>{i.n ?? "…"}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function CatalogInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const qs = params.toString();
  const isNetworks = params.get("kind") === "networks";
  const [open, setOpen] = useState(false);
  const [counts, setCounts] = useState<Counts>();
  const filtersBtn = useRef<HTMLButtonElement>(null);
  const [state, setState] = useState<{ loading: boolean; offers?: Page<OfferT>; nets?: Page<NetT>; error?: string }>({ loading: true });

  useEffect(() => void getCatalogCounts().then(setCounts).catch(() => {}), []);
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
  const sortLink = (asc: string, desc: string) => {
    const p = new URLSearchParams(qs);
    p.set("sort", params.get("sort") === desc ? asc : desc);
    return `${pathname}?${p}`;
  };
  const close = () => {
    setOpen(false);
    filtersBtn.current?.focus({ preventScroll: true });
  };
  const active = [...params.keys()].filter((k) => !OUTSIDE.has(k) && k !== "platform").length;
  const count = state.offers?.count ?? state.nets?.count ?? 0;
  const section = isNetworks ? "networks" : params.get("platform") === "tiktok" ? "tiktok" : params.get("platform") === "youtube" ? "youtube" : "all";
  const titles: Record<string, string> = {
    all: "Реклама в коротких видео", tiktok: "Реклама в TikTok", youtube: "Реклама в YouTube Shorts", networks: "Рекламные сетки",
  };

  return (
    <div className="flex flex-col gap-6">
      <section className="relative -mt-8 overflow-hidden pt-8">
        {/* decorative disc, FunPay-style; clipped by the section so the page never scrolls sideways */}
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-28 hidden h-[24rem] w-[24rem] rounded-full bg-[conic-gradient(from_200deg,#ff3d5a,#7c4dff,#00a3ff,#ff3d5a)] lg:block" />
        <div aria-hidden className="pointer-events-none absolute -right-10 -top-14 hidden h-[20rem] w-[20rem] rounded-full border-[18px] border-surface/25 lg:block" />
        <div className="relative max-w-2xl">
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{titles[section]}</h1>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Покупайте рекламу напрямую у авторов TikTok и YouTube Shorts — подписчики и просмотры получены из самих платформ.{" "}
            <b className="text-text">Продавец получает оплату только после того, как вы подтвердите выполнение заказа</b>{" "}
            (подробнее — в разделе <Link href="/support" className="text-accent hover:underline">«Помощь»</Link>).
          </p>
        </div>
        <div className="relative mt-6"><Bubbles counts={counts} active={section} /></div>
      </section>

      <div className="flex flex-wrap items-center gap-2">
        <Toggle label="Только продавцы онлайн" on={params.get("online") === "1"} onChange={(v) => setParam("online", v ? "1" : "")} />
        {!isNetworks && <Toggle label="✓ Данные платформы" on={params.get("verified") === "1"} onChange={(v) => setParam("verified", v ? "1" : "")} />}
        <form
          key={params.get("q") ?? ""}
          onSubmit={(e) => {
            e.preventDefault();
            setParam("q", String(new FormData(e.currentTarget).get("q") ?? "").trim());
          }}
          className="relative min-w-0 flex-[1_1_14rem]"
          role="search"
        >
          <input name="q" defaultValue={params.get("q") ?? ""} placeholder="Поиск по описанию" aria-label="Поиск по каталогу" className={`${input} pr-9`} />
          <button aria-label="Найти" className="absolute right-1 top-1/2 -translate-y-1/2 p-2 text-muted hover:text-text">
            <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          </button>
        </form>
        <button
          ref={filtersBtn}
          type="button"
          onClick={() => setOpen(true)}
          aria-expanded={open}
          aria-haspopup="dialog"
          className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:border-accent"
        >
          <svg aria-hidden width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h16M7 12h10M10 18h4" /></svg>
          Фильтры
          {active > 0 && <span className="rounded-full bg-accent px-1.5 text-xs text-accent-ink">{active}</span>}
        </button>
        <Link href="/account/accounts/new" className="ml-auto rounded-lg border border-border px-4 py-2 text-sm font-semibold text-accent hover:border-accent">
          Продать рекламу
        </Link>
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
      {!state.loading && count > 0 && (
        <OfferTable
          offers={state.offers?.results}
          networks={state.nets?.results}
          sortHref={isNetworks ? undefined : {
            price: sortLink("price_asc", "price_desc"), followers: sortLink("followers", "followers"),
            views: sortLink("views", "views"), active: params.get("sort") ?? "",
          }}
        />
      )}
    </div>
  );
}

export default function CatalogPage() {
  return <Suspense><CatalogInner /></Suspense>;
}
