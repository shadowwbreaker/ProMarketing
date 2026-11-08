"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { DirectChat } from "@/components/profile/DirectChat";
import { OfferExtras } from "@/components/OfferExtras";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { getOfferCard, OfferCard } from "@/lib/api/public";
import { PLATFORM_LABEL } from "@/lib/api/social";
import { fieldErrors } from "@/lib/forms";
import { formatCount, formatDateTime, formatMoney, reviewsWord } from "@/lib/format";

const Label = ({ children }: { children: React.ReactNode }) => (
  <h2 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">{children}</h2>
);

/** Offer page in FunPay's "Оформление заказа" layout: the deal on the left, the seller chat on the right. */
export default function OfferPage() {
  const { id } = useParams<{ id: string }>();
  const [o, setO] = useState<OfferCard>();
  const [err, setErr] = useState<string>();
  const [pick, setPick] = useState<string>();
  useEffect(() => {
    getOfferCard(id).then((x) => { setO(x); setPick(x.offers?.[0]?.id); }).catch((e) => setErr(fieldErrors(e).form));
  }, [id]);
  if (err) return <ErrorState message={err} />;
  if (!o) return <LoadingState />;
  const offer = o.offers?.find((x) => x.id === pick);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_420px]">
      <div className="max-w-xl">
        <Link href={`/catalog?platform=${o.platform}`} className="text-sm text-muted hover:text-accent">‹ {PLATFORM_LABEL[o.platform]}</Link>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">Оформление заказа</h1>

        <div className="mt-6 flex flex-col gap-6">
          <section>
            <Label>Канал</Label>
            <p className="text-sm">
              {PLATFORM_LABEL[o.platform]} ·{" "}
              <a href={o.profile_url} target="_blank" rel="noopener noreferrer nofollow" className="font-semibold text-accent hover:underline">@{o.handle}</a>
              {o.ownership_verified && <span className="ml-2 text-xs text-ok">✓ владение подтверждено</span>}
            </p>
          </section>

          <section>
            <Label>Краткое описание</Label>
            <p className="text-base font-medium">{o.title}</p>
          </section>

          <section>
            <Label>Статистика</Label>
            <dl className="grid grid-cols-2 gap-4">
              <div><dd className="text-2xl font-bold tabular-nums">{o.followers != null ? formatCount(o.followers) : "—"}</dd><dt className="text-xs text-muted">подписчиков</dt></div>
              <div>
                <dd className="text-2xl font-bold tabular-nums">{o.avg_views != null ? formatCount(o.avg_views) : "—"}</dd>
                <dt className="text-xs text-muted">{o.avg_views != null ? `просмотров на видео, среднее по ${o.videos_in_sample}` : "просмотры скрыты до одобрения YouTube"}</dt>
              </div>
            </dl>
            <p className="mt-2 text-xs text-muted">
              {o.trust_status === "VERIFIED" ? "✓ Получено из официального API платформы" : o.trust_status === "MANUAL" ? "Указано продавцом вручную" : "Данные могли устареть"}
              {o.stats_updated_at && ` · ${formatDateTime(o.stats_updated_at)}`}
            </p>
          </section>

          {(o.description || o.category || o.geo) && (
            <section>
              <Label>Подробное описание</Label>
              {(o.category || o.geo) && <p className="mb-1 text-sm text-muted">{[o.category, o.geo].filter(Boolean).join(" · ")}</p>}
              {o.description && <p className="whitespace-pre-line text-sm leading-relaxed">{o.description}</p>}
            </section>
          )}

          <section>
            <Label>Формат рекламы</Label>
            <label className="sr-only" htmlFor="offer-pick">Формат рекламы</label>
            <select id="offer-pick" value={pick} onChange={(e) => setPick(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-4 py-3 text-sm">
              {o.offers?.map((x) => <option key={x.id} value={x.id}>{x.ad_format_label} — {formatMoney(x.price_minor)}</option>)}
            </select>
            {offer && (
              <div className="mt-3 text-sm">
                <p className="text-muted">Публикация в течение {offer.publish_within_days} дн. · ролик держится {offer.placement_days} дн.</p>
                {offer.conditions && <p className="mt-2 whitespace-pre-line leading-relaxed">{offer.conditions}</p>}
              </div>
            )}
          </section>

          <section>
            {offer && (
              <Link href={`/orders/new?offer=${offer.id}`}
                className="block rounded-lg bg-accent px-4 py-3 text-center font-semibold text-accent-ink transition-[scale] duration-150 active:scale-[0.96] motion-reduce:active:scale-100">
                Купить за {formatMoney(offer.price_minor)}
              </Link>
            )}
            <p className="mt-3 text-sm text-muted">
              Продавец не сможет получить оплату до тех пор, пока вы не подтвердите выполнение им всех обязательств.
            </p>
            <div className="mt-3"><OfferExtras accountId={o.id} /></div>
          </section>

          <section className="border-t border-border pt-6">
            <Label>Рейтинг продавца</Label>
            <div className="flex items-center gap-4">
              <p className="text-4xl font-extrabold">{o.seller.rating != null ? o.seller.rating.toFixed(1).replace(/\.0$/, "") : "—"}<span className="ml-1 text-sm font-bold">из 5</span></p>
              <Link href={`/sellers/${o.seller.id}#reviews`} className="text-sm font-semibold text-accent hover:underline">
                {o.seller.reviews_count} {reviewsWord(o.seller.reviews_count)}
              </Link>
            </div>
          </section>
        </div>
      </div>

      <DirectChat userId={o.seller.id} avatar={o.seller.avatar_url} name={o.seller.display_name}
        online={!!o.seller.online} rating={o.seller.rating} reviews={o.seller.reviews_count} />
    </div>
  );
}
