"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CardGrid, NetworkCard, OfferCard } from "@/components/catalog/Cards";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { getSeller, SellerPage } from "@/lib/api/public";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";

export default function SellerProfilePage() {
  const { id } = useParams<{ id: string }>();
  const [s, setS] = useState<SellerPage>();
  const [err, setErr] = useState<string>();
  useEffect(() => {
    getSeller(id).then(setS).catch((e) => setErr(fieldErrors(e).form));
  }, [id]);
  if (err) return <ErrorState message={err} />;
  if (!s) return <LoadingState />;
  return (
    <div className="flex flex-col gap-6">
      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold">{s.display_name}</h1>
          {s.bio && <p className="mt-1 max-w-xl text-sm text-muted">{s.bio}</p>}
          <p className="mt-2 text-xs text-muted">
            На платформе с {formatDateTime(s.member_since)}{s.last_seen_at && ` · был(а) ${formatDateTime(s.last_seen_at)}`}
          </p>
        </div>
        <div className="flex gap-6 text-center">
          <div><p className="text-2xl font-bold">{s.rating != null ? `★ ${s.rating.toFixed(1)}` : "—"}</p><p className="text-xs text-muted">{s.reviews_count} отзывов</p></div>
          <div><p className="text-2xl font-bold">{s.completed_orders}</p><p className="text-xs text-muted">выполнено заказов</p></div>
        </div>
      </Card>
      <h2 className="text-xl font-bold">Аккаунты</h2>
      {s.accounts.length ? <CardGrid>{s.accounts.map((o) => <OfferCard key={o.id} o={o} />)}</CardGrid> : <EmptyState title="Нет активных предложений" />}
      {s.networks.length > 0 && (<><h2 className="text-xl font-bold">Сетки</h2><CardGrid>{s.networks.map((n) => <NetworkCard key={n.id} n={n} />)}</CardGrid></>)}
      <h2 className="text-xl font-bold">Отзывы</h2>
      {s.reviews.length ? (
        <ul className="flex flex-col gap-3">
          {s.reviews.map((r) => (
            <li key={r.id}><Card>
              <p className="text-sm font-semibold">{"★".repeat(r.rating)}<span className="text-muted">{"★".repeat(5 - r.rating)}</span> · {r.author}</p>
              {r.text && <p className="mt-1 text-sm">{r.text}</p>}
              {r.seller_reply && <p className="mt-2 border-l-2 border-border pl-3 text-sm text-muted">Ответ продавца: {r.seller_reply}</p>}
            </Card></li>
          ))}
        </ul>
      ) : <EmptyState title="Отзывов пока нет" />}
    </div>
  );
}
