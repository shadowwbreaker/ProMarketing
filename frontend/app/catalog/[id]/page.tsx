"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Metric, SellerLine } from "@/components/catalog/Cards";
import { Avatar } from "@/components/profile/Avatar";
import { OfferExtras } from "@/components/OfferExtras";
import { TrustBadge } from "@/components/stats/TrustBadge";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { getOfferCard, OfferCard } from "@/lib/api/public";
import { PLATFORM_LABEL } from "@/lib/api/social";
import { fieldErrors } from "@/lib/forms";
import { formatCount, formatDateTime, formatMoney } from "@/lib/format";

export default function OfferPage() {
  const { id } = useParams<{ id: string }>();
  const [o, setO] = useState<OfferCard>();
  const [err, setErr] = useState<string>();
  useEffect(() => {
    getOfferCard(id).then(setO).catch((e) => setErr(fieldErrors(e).form));
  }, [id]);
  if (err) return <ErrorState message={err} />;
  if (!o) return <LoadingState />;
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="flex flex-col gap-4">
        <div>
          <p className="text-sm text-muted">{PLATFORM_LABEL[o.platform]} {o.category && `· ${o.category}`} {o.geo && `· ${o.geo}`}</p>
          <h1 className="text-3xl font-extrabold">{o.title}</h1>
          <a href={o.profile_url} target="_blank" rel="noopener noreferrer nofollow" className="text-accent">@{o.handle}</a>
          {o.ownership_verified && <span className="ml-2 text-xs text-ok">владение подтверждено</span>}
        </div>
        <OfferExtras accountId={o.id} />
        <Card className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Metric label="Подписчики" value={o.followers != null ? formatCount(o.followers) : "—"} />
          <Metric label="Средние просмотры" value={o.avg_views != null ? formatCount(o.avg_views) : "—"} sub={o.avg_views == null && o.derived_metrics_note ? "скрыто до одобрения YouTube" : undefined} />
          <Metric label="Видео в выборке" value={String(o.videos_in_sample)} />
          <div>
            <p className="text-[11px] uppercase tracking-wide text-muted">Статистика</p>
            <TrustBadge status={o.trust_status} />
            <p className="text-[11px] text-muted">{o.stats_updated_at ? formatDateTime(o.stats_updated_at) : "нет данных"}</p>
          </div>
        </Card>
        {o.derived_metrics_note && <p className="text-sm text-muted">{o.derived_metrics_note}</p>}
        <Card>
          <h2 className="mb-3 font-bold">Как проходит сделка</h2>
          <ol className="grid gap-3 text-sm sm:grid-cols-4">
            {[
              ["Оплата", "Деньги удерживает платёжный провайдер, продавец их пока не получает"],
              ["Публикация", "Продавец выкладывает ролик и присылает ссылку"],
              ["Проверка", "Вы подтверждаете выполнение или открываете спор"],
              ["Выплата", "Через 48 часов после подтверждения деньги уходят продавцу"],
            ].map(([t, d], i) => (
              <li key={t}><p className="font-semibold"><span className="text-accent">{i + 1}.</span> {t}</p><p className="mt-1 text-muted">{d}</p></li>
            ))}
          </ol>
        </Card>
        {o.description && <Card><h2 className="mb-2 font-bold">Об аккаунте</h2><p className="whitespace-pre-line text-sm">{o.description}</p></Card>}
      </div>
      <aside className="flex flex-col gap-3">
        <Card className="flex items-center gap-3">
          <Avatar id={o.seller.id} name={o.seller.display_name} size={44} src={o.seller.avatar_url} />
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted">Продавец</p>
            <SellerLine s={o.seller} />
          </div>
          <Link href={`/sellers/${o.seller.id}`} className="shrink-0 rounded-lg border border-border px-3 py-1.5 text-sm font-semibold hover:border-accent">
            Написать
          </Link>
        </Card>
        {o.offers?.map((of) => (
          <Card key={of.id}>
            <p className="text-sm font-semibold">{of.ad_format_label}</p>
            <p className="text-2xl font-extrabold">{formatMoney(of.price_minor)}</p>
            <p className="text-xs text-muted">Публикация в течение {of.publish_within_days} дн. · держится {of.placement_days} дн.</p>
            {of.conditions && <p className="mt-2 whitespace-pre-line text-sm">{of.conditions}</p>}
            <Link href={`/orders/new?offer=${of.id}`} className="mt-3 block rounded-lg bg-accent px-4 py-2 text-center font-semibold text-accent-ink">
              Заказать
            </Link>
          </Card>
        ))}
      </aside>
    </div>
  );
}
