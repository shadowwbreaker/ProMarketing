"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Metric, SellerLine } from "@/components/catalog/Cards";
import { OfferTable } from "@/components/catalog/OfferTable";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { getNetworkCard, NetworkCard } from "@/lib/api/public";
import { fieldErrors } from "@/lib/forms";
import { formatCount, formatMoney } from "@/lib/format";

export default function NetworkPage() {
  const { id } = useParams<{ id: string }>();
  const [n, setN] = useState<NetworkCard>();
  const [err, setErr] = useState<string>();
  useEffect(() => {
    getNetworkCard(id).then(setN).catch((e) => setErr(fieldErrors(e).form));
  }, [id]);
  if (err) return <ErrorState message={err} />;
  if (!n) return <LoadingState />;
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-sm text-muted">Рекламная сетка · {n.stats.accounts} каналов</p>
        <h1 className="text-3xl font-extrabold">{n.title}</h1>
        <SellerLine s={n.seller} />
      </div>
      <Card className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric label="Подписчиков" value={formatCount(n.stats.total_followers)} />
        <Metric label="Сумма ср. просмотров" value={formatCount(n.stats.total_avg_views)} />
        <Metric label="Подтверждённых" value={`${n.stats.verified_accounts} из ${n.stats.accounts}`} />
        <Metric label="Цена сетки" value={formatMoney(n.stats.price_minor)} sub={n.stats.price_minor !== n.stats.items_price_minor ? `по отдельности ${formatMoney(n.stats.items_price_minor)}` : undefined} />
      </Card>
      {n.description && <p className="whitespace-pre-line">{n.description}</p>}
      {n.conditions && <Card><h2 className="mb-1 font-bold">Условия</h2><p className="whitespace-pre-line text-sm">{n.conditions}</p></Card>}
      <Link href={`/orders/new?network=${n.id}`} className="self-start rounded-lg bg-accent px-5 py-3 font-semibold text-accent-ink">Заказать всю сетку</Link>
      <h2 className="text-xl font-bold">Каналы сетки{n.allow_partial_purchase && <span className="text-sm font-normal text-muted"> — можно заказать по отдельности</span>}</h2>
      <OfferTable offers={n.items?.map((i) => i.account) ?? []} />
    </div>
  );
}
