import Link from "next/link";
import { Avatar } from "@/components/profile/Avatar";
import type { NetworkCard, OfferCard, SellerBrief } from "@/lib/api/public";
import { PLATFORM_LABEL } from "@/lib/api/social";
import { formatCount, formatMoney, timeAgo } from "@/lib/format";

const PLATFORM_DOT: Record<string, string> = { tiktok: "bg-text", youtube: "bg-[#ff0033]", instagram: "bg-accent" };

function Stars({ rating }: { rating: number }) {
  const full = Math.round(rating);
  return (
    <span className="tracking-tighter" aria-label={`Рейтинг ${rating.toFixed(1)} из 5`}>
      <span className="text-[#f5c518]">{"★".repeat(full)}</span><span className="text-border">{"★".repeat(5 - full)}</span>
    </span>
  );
}

export function SellerCell({ s }: { s: SellerBrief }) {
  return (
    <Link href={`/sellers/${s.id}`} className="relative z-10 flex min-w-0 items-center gap-2.5 hover:text-accent">
      <span className="relative shrink-0">
        <Avatar id={s.id} name={s.display_name} size={36} src={s.avatar_url} />
        <span aria-label={s.online ? "онлайн" : "не в сети"}
          className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-surface ${s.online ? "bg-[#4caf50]" : "bg-[#b8bcc4]"}`} />
      </span>
      <span className="min-w-0 leading-tight">
        <span className={`block truncate text-sm font-semibold ${s.online ? "" : "text-muted"}`}>{s.display_name}</span>
        <span className="block text-xs text-muted">
          {s.rating != null ? <><Stars rating={s.rating} /> {s.reviews_count}</> : "нет отзывов"}
        </span>
        {s.member_since && <span className="block text-xs text-muted">на сайте {timeAgo(s.member_since).replace(" назад", "")}</span>}
      </span>
    </Link>
  );
}

/** @handle opens the channel itself on TikTok/YouTube (new tab), above the row's stretched link. */
export function ChannelLink({ url, handle, verified }: { url: string; handle: string; verified?: boolean }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer nofollow" title="Открыть канал на платформе"
      className="relative z-10 inline-flex items-center gap-0.5 underline decoration-border underline-offset-2 transition-colors duration-150 hover:text-accent hover:decoration-accent">
      @{handle}
      {verified && <span className="text-ok no-underline" title="Владение каналом подтверждено"> ✓</span>}
      <span aria-hidden className="text-[10px]">↗</span>
    </a>
  );
}

function PlatformTag({ p }: { p: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted">
      <span className={`h-1.5 w-1.5 rounded-full ${PLATFORM_DOT[p] ?? "bg-muted"}`} aria-hidden />{PLATFORM_LABEL[p] ?? p}
    </span>
  );
}

const row = "group relative grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 rounded-xl px-3 py-3.5 transition-colors duration-150 hover:bg-bg sm:grid-cols-[minmax(0,1fr)_7rem_7rem_13rem_7.5rem] sm:items-center";
const stretched = "after:absolute after:inset-0 after:content-[''] focus-visible:outline-none";

export function OfferRow({ o }: { o: OfferCard }) {
  return (
    <li className={`${row} has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-accent`}>
      <div className="min-w-0">
        <Link href={`/catalog/${o.id}`} className={`line-clamp-2 font-medium ${stretched}`}>{o.title}</Link>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
          <PlatformTag p={o.platform} />
          <ChannelLink url={o.profile_url} handle={o.handle} verified={o.ownership_verified} />
          {o.trust_status === "MANUAL" && <span className="text-warn">цифры указаны вручную</span>}
          {o.trust_status === "STALE" && <span>данные устарели</span>}
          <span className="sm:hidden">· {o.followers != null ? formatCount(o.followers) : "—"} подп.</span>
        </p>
      </div>
      <p className="hidden text-right text-sm tabular-nums sm:block">{o.followers != null ? formatCount(o.followers) : "—"}</p>
      <p className="hidden text-right text-sm tabular-nums sm:block" title={o.avg_views == null && o.derived_metrics_note ? o.derived_metrics_note : undefined}>
        {o.avg_views != null ? formatCount(o.avg_views) : <span className="text-muted">скрыто</span>}
      </p>
      <div className="col-span-2 row-start-2 sm:col-span-1 sm:row-start-auto"><SellerCell s={o.seller} /></div>
      <p className="col-start-2 row-start-1 text-right sm:col-start-auto sm:row-start-auto">
        <span className="inline-block whitespace-nowrap rounded-lg bg-bg px-2.5 py-1 font-bold tabular-nums transition-colors duration-150 group-hover:bg-accent group-hover:text-accent-ink">
          {o.min_price_minor != null ? formatMoney(o.min_price_minor) : "—"}
        </span>
      </p>
    </li>
  );
}

export function NetworkRow({ n }: { n: NetworkCard }) {
  return (
    <li className={`${row} has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-accent`}>
      <div className="min-w-0">
        <Link href={`/catalog/networks/${n.id}`} className={`line-clamp-2 font-medium ${stretched}`}>{n.title}</Link>
        <p className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-muted">
          <span>Сетка · {n.stats.accounts} каналов</span>
          {n.platforms.map((p) => <PlatformTag key={p} p={p} />)}
        </p>
      </div>
      <p className="hidden text-right text-sm tabular-nums sm:block">{formatCount(n.stats.total_followers)}</p>
      <p className="hidden text-right text-sm tabular-nums sm:block">{formatCount(n.stats.total_avg_views)}</p>
      <div className="col-span-2 row-start-2 sm:col-span-1 sm:row-start-auto"><SellerCell s={n.seller} /></div>
      <p className="col-start-2 row-start-1 text-right sm:col-start-auto sm:row-start-auto">
        <span className="inline-block whitespace-nowrap rounded-lg bg-bg px-2.5 py-1 font-bold tabular-nums transition-colors duration-150 group-hover:bg-accent group-hover:text-accent-ink">{formatMoney(n.stats.price_minor)}</span>
      </p>
    </li>
  );
}

/** FunPay-style list: description · subscribers · views · seller · price. */
export function OfferTable({ offers = [], networks = [], sortHref }: {
  offers?: OfferCard[];
  networks?: NetworkCard[];
  sortHref?: { price: string; followers: string; views: string; active?: string };
}) {
  const head = (label: string, key?: "price" | "followers" | "views") =>
    key && sortHref ? (
      <Link href={sortHref[key]} className="inline-flex items-center gap-1 hover:text-accent" aria-label={`Сортировать: ${label}`}>
        {label} <span aria-hidden className={`transition-colors duration-150 ${sortHref.active?.startsWith(key) ? "text-accent" : "text-muted/60"}`}>⇅</span>
      </Link>
    ) : label;
  return (
    <div>
      <div className="hidden grid-cols-[minmax(0,1fr)_7rem_7rem_13rem_7.5rem] gap-x-4 px-3 pb-2 text-[11px] font-bold uppercase tracking-wider text-muted sm:grid">
        <span>Описание</span>
        <span className="text-right">{head("Подписчики", "followers")}</span>
        <span className="text-right">{head("Просмотры", "views")}</span>
        <span>Продавец</span>
        <span className="text-right">{head("Цена", "price")}</span>
      </div>
      <ul className="rows divide-y divide-border/70 border-y border-border/70">
        {offers.map((o) => <OfferRow key={o.id} o={o} />)}
        {networks.map((n) => <NetworkRow key={n.id} n={n} />)}
      </ul>
    </div>
  );
}
