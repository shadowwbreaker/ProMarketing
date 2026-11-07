"use client";

import { useEffect, useState } from "react";
import { CardGrid, NetworkCard, OfferCard } from "@/components/catalog/Cards";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { fieldErrors } from "@/lib/forms";
import { Analytics, getAnalytics, getFavorites, getRecommendations, getReferrals, getViewed } from "@/lib/api/insights";
import type { NetworkCard as N, OfferCard as O } from "@/lib/api/public";
import { formatMoney } from "@/lib/format";

function Grid({ load, empty }: { load: () => Promise<O[]>; empty: string }) {
  const [rows, setRows] = useState<O[]>();
  const [err, setErr] = useState<string>();
  useEffect(() => void load().then(setRows).catch((e) => setErr(fieldErrors(e).form)), [load]);
  if (err) return <ErrorState message={err} />;
  if (!rows) return <LoadingState />;
  if (!rows.length) return <EmptyState title={empty} />;
  return <CardGrid>{rows.map((o) => <OfferCard key={o.id} o={o} />)}</CardGrid>;
}

export const ViewedPanel = () => <Grid load={getViewed} empty="Вы ещё не открывали предложения" />;
export const RecommendationsPanel = () => <Grid load={getRecommendations} empty="Пока нечего рекомендовать — откройте несколько предложений в каталоге" />;

export function FavoritesPanel() {
  const [d, setD] = useState<{ accounts: O[]; networks: N[] }>();
  const [err, setErr] = useState<string>();
  useEffect(() => void getFavorites().then(setD).catch((e) => setErr(fieldErrors(e).form)), []);
  if (err) return <ErrorState message={err} />;
  if (!d) return <LoadingState />;
  if (!d.accounts.length && !d.networks.length) return <EmptyState title="В избранном пусто" />;
  return <CardGrid>{d.accounts.map((o) => <OfferCard key={o.id} o={o} />)}{d.networks.map((n) => <NetworkCard key={n.id} n={n} />)}</CardGrid>;
}

const Stat = ({ label, value }: { label: string; value: string }) => (
  <Card><p className="text-xs text-muted">{label}</p><p className="text-xl font-bold">{value}</p></Card>
);

export function AnalyticsPanel() {
  const [a, setA] = useState<Analytics>();
  const [err, setErr] = useState<string>();
  useEffect(() => void getAnalytics().then(setA).catch((e) => setErr(fieldErrors(e).form)), []);
  if (err) return <ErrorState message={err} />;
  if (!a) return <LoadingState />;
  const b = a.buyer;
  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-bold">Как покупатель</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Оплачено заказов" value={String(b.orders_paid)} />
        <Stat label="Потрачено (за вычетом возвратов)" value={formatMoney(b.net_spent_minor)} />
        <Stat label="Просмотров за 30 дней (по отчётам)" value={b.views_30d_total.toLocaleString("ru-RU")} />
        <Stat label="Цена 1000 просмотров" value={b.cost_per_1000_views_minor != null ? formatMoney(b.cost_per_1000_views_minor) : "—"} />
      </div>
      {a.seller && (
        <>
          <h2 className="font-bold">Как продавец</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Выполнено позиций" value={`${a.seller.items_completed} из ${a.seller.items_total}`} />
            <Stat label="Доход после комиссии" value={formatMoney(a.seller.revenue_minor)} />
            <Stat label="Доля выполненных" value={a.seller.completion_rate_pct != null ? `${a.seller.completion_rate_pct}%` : "—"} />
            <Stat label="Среднее время принятия" value={a.seller.avg_accept_hours != null ? `${a.seller.avg_accept_hours} ч` : "—"} />
          </div>
          {a.seller.by_account.length > 0 && (
            <ul className="text-sm">{a.seller.by_account.map((r) => <li key={r.social_account__title}>{r.social_account__title}: {r.n} заказов · {formatMoney(r.revenue)}</li>)}</ul>
          )}
        </>
      )}
    </div>
  );
}

export function ReferralsPanel() {
  const [r, setR] = useState<{ code: string; invited: number; reward_policy: string }>();
  const [err, setErr] = useState<string>();
  useEffect(() => void getReferrals().then(setR).catch((e) => setErr(fieldErrors(e).form)), []);
  if (err) return <ErrorState message={err} />;
  if (!r) return <LoadingState />;
  const link = `${typeof window !== "undefined" ? window.location.origin : ""}/register?ref=${r.code}`;
  return (
    <Card>
      <h2 className="mb-2 font-bold">Пригласить на платформу</h2>
      <p className="break-all text-sm">Ваша ссылка: <code>{link}</code></p>
      <p className="mt-2 text-sm">Зарегистрировалось по ссылке: <b>{r.invited}</b></p>
      <p className="mt-2 text-xs text-muted">{r.reward_policy}</p>
    </Card>
  );
}
