import Link from "next/link";
import { TrustBadge } from "@/components/stats/TrustBadge";
import type { NetworkCard as NetworkCardT, OfferCard as OfferCardT, SellerBrief } from "@/lib/api/public";
import { PLATFORM_LABEL } from "@/lib/api/social";
import { formatCount, formatDateTime, formatMoney } from "@/lib/format";

const PLATFORM_DOT: Record<string, string> = { tiktok: "bg-text", youtube: "bg-danger", instagram: "bg-accent" };

export function SellerLine({ s }: { s: SellerBrief }) {
  return (
    <Link href={`/sellers/${s.id}`} className="text-xs text-muted hover:text-accent">
      {s.display_name} · {s.rating != null ? `★ ${s.rating.toFixed(1)} (${s.reviews_count})` : "нет отзывов"}
    </Link>
  );
}

export function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="text-lg font-bold leading-tight">{value}</p>
      {sub && <p className="text-[11px] text-muted">{sub}</p>}
    </div>
  );
}

export function OfferCard({ o }: { o: OfferCardT }) {
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 transition hover:border-accent">
      <div className="flex items-center justify-between gap-2">
        <p className="flex min-w-0 items-center gap-1.5 truncate text-xs text-muted">
          <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${PLATFORM_DOT[o.platform]}`} />
          <span className="truncate">{PLATFORM_LABEL[o.platform]}{o.category && <> · {o.category}</>}</span>
        </p>
        <TrustBadge status={o.trust_status} />
      </div>
      <div className="min-w-0">
        <Link href={`/catalog/${o.id}`} className="line-clamp-2 font-semibold hover:text-accent" title={o.title}>{o.title}</Link>
        <p className="truncate text-xs text-muted">@{o.handle}{o.ownership_verified && <span className="text-ok" title="Владение подтверждено"> ✓</span>}</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Metric label="Подписчики" value={o.followers != null ? formatCount(o.followers) : "—"} />
        <Metric label="Ср. просмотры" value={o.avg_views != null ? formatCount(o.avg_views) : "—"}
          sub={o.avg_views != null ? `по ${o.videos_in_sample} видео` : o.derived_metrics_note ? "скрыто до одобрения YouTube" : undefined} />
      </div>
      <div className="mt-auto">
        <p className="text-xl font-extrabold"><span className="text-xs font-normal text-muted">от </span>{o.min_price_minor != null ? formatMoney(o.min_price_minor) : "—"}</p>
        <SellerLine s={o.seller} />
      </div>
      {o.stats_updated_at && <p className="text-[11px] text-muted">Статистика от {formatDateTime(o.stats_updated_at)}</p>}
    </article>
  );
}

export function NetworkCard({ n }: { n: NetworkCardT }) {
  return (
    <article className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4 hover:border-accent">
      <p className="text-xs text-muted">Сетка · {n.stats.accounts} аккаунтов · {n.platforms.map((p) => PLATFORM_LABEL[p]).join(", ")}</p>
      <Link href={`/catalog/networks/${n.id}`} className="font-semibold hover:text-accent">{n.title}</Link>
      <div className="grid grid-cols-2 gap-2">
        <Metric label="Подписчиков" value={formatCount(n.stats.total_followers)} />
        <Metric label="Сумма ср. просмотров" value={formatCount(n.stats.total_avg_views)} />
      </div>
      <div className="flex items-end justify-between">
        <p className="text-xl font-extrabold">{formatMoney(n.stats.price_minor)}</p>
        <SellerLine s={n.seller} />
      </div>
    </article>
  );
}

export function CardGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(230px,1fr))]">{children}</div>;
}
