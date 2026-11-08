import Link from "next/link";
import { Avatar } from "@/components/profile/Avatar";
import type { NetworkCard as NetworkCardT, OfferCard as OfferCardT, SellerBrief } from "@/lib/api/public";
import { PLATFORM_LABEL } from "@/lib/api/social";
import { formatCount, formatMoney } from "@/lib/format";

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

const STATUS_NOTE: Partial<Record<OfferCardT["trust_status"], { text: string; cls: string; hint: string }>> = {
  MANUAL: { text: "Указано вручную", cls: "text-warn", hint: "Введено владельцем, платформой не проверено" },
  STALE: { text: "Данные устарели", cls: "text-muted", hint: "Статистика давно не обновлялась" },
  SUSPICIOUS: { text: "На проверке", cls: "text-danger", hint: "Обнаружены подозрительные изменения" },
};

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xl font-bold tabular-nums leading-none">{value}</p>
      <p className="mt-1 text-xs text-muted">{label}</p>
    </div>
  );
}

function SellerChip({ s }: { s: SellerBrief }) {
  return (
    <Link href={`/sellers/${s.id}`} className="relative z-10 flex min-w-0 items-center gap-1.5 self-start text-xs text-muted hover:text-accent">
      <Avatar id={s.id} name={s.display_name} size={20} src={s.avatar_url} />
      <span className="truncate">{s.display_name}</span>
      <span className="shrink-0">{s.rating != null ? `★ ${s.rating.toFixed(1)}` : "· нет отзывов"}</span>
    </Link>
  );
}

/** Catalog card: what it is, how big it is, how much it costs. Everything else lives on the offer page. */
export function OfferCard({ o }: { o: OfferCardT }) {
  const note = STATUS_NOTE[o.trust_status];
  return (
    <article className="group relative flex flex-col rounded-2xl border border-border bg-surface p-4 transition-[border-color,box-shadow] duration-150 hover:border-accent/60 hover:shadow-md has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-accent">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-bg px-2 py-0.5 font-medium">
          <span className={`h-1.5 w-1.5 rounded-full ${PLATFORM_DOT[o.platform]}`} aria-hidden />
          {PLATFORM_LABEL[o.platform]}
          {o.trust_status === "VERIFIED" && <span className="text-ok" title="Цифры получены из официального API платформы">✓</span>}
        </span>
        {o.category && <span className="truncate text-muted">{o.category}</span>}
      </div>

      <h3 className="mt-3 line-clamp-2 text-base font-semibold leading-snug" title={o.title}>
        <Link href={`/catalog/${o.id}`} className="after:absolute after:inset-0 after:rounded-2xl after:content-[''] focus-visible:outline-none">
          {o.title}
        </Link>
      </h3>
      <p className="truncate text-sm text-muted">
        @{o.handle}
        {o.ownership_verified && <span className="text-ok" title="Владение аккаунтом подтверждено"> ✓</span>}
      </p>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <Stat value={o.followers != null ? formatCount(o.followers) : "—"} label="подписчиков" />
        <Stat
          value={o.avg_views != null ? formatCount(o.avg_views) : "—"}
          label={o.avg_views != null ? "просмотров на видео" : o.derived_metrics_note ? "просмотры скрыты" : "просмотров"}
        />
      </div>
      {note && <p className={`mt-2 text-xs font-medium ${note.cls}`} title={note.hint}>{note.text}</p>}

      <div className="mt-auto pt-4">
        <div className="flex flex-col gap-2 border-t border-border pt-3">
          <p className="text-lg font-extrabold tabular-nums">
            {o.min_price_minor != null ? <><span className="text-sm font-medium text-muted">от </span>{formatMoney(o.min_price_minor)}</> : "—"}
          </p>
          <SellerChip s={o.seller} />
        </div>
      </div>
    </article>
  );
}

export function NetworkCard({ n }: { n: NetworkCardT }) {
  return (
    <article className="group relative flex flex-col rounded-2xl border border-border bg-surface p-4 transition-[border-color,box-shadow] duration-150 hover:border-accent/60 hover:shadow-md has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-accent">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="rounded-full bg-bg px-2 py-0.5 font-medium">Сетка · {n.stats.accounts} акк.</span>
        <span className="truncate text-muted">{n.platforms.map((p) => PLATFORM_LABEL[p]).join(", ")}</span>
      </div>
      <h3 className="mt-3 line-clamp-2 text-base font-semibold leading-snug">
        <Link href={`/catalog/networks/${n.id}`} className="after:absolute after:inset-0 after:rounded-2xl after:content-['']">{n.title}</Link>
      </h3>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <Stat value={formatCount(n.stats.total_followers)} label="подписчиков всего" />
        <Stat value={formatCount(n.stats.total_avg_views)} label="просмотров на видео (сумма)" />
      </div>
      <div className="mt-auto pt-4">
        <div className="flex flex-col gap-2 border-t border-border pt-3">
          <p className="text-lg font-extrabold tabular-nums">{formatMoney(n.stats.price_minor)}</p>
          <SellerChip s={n.seller} />
        </div>
      </div>
    </article>
  );
}

export function CardGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(230px,1fr))]">{children}</div>;
}
