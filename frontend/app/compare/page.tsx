"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { TrustBadge } from "@/components/stats/TrustBadge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { compare, getCompareList, setCompareList } from "@/lib/api/insights";
import type { OfferCard } from "@/lib/api/public";
import { PLATFORM_LABEL } from "@/lib/api/social";
import { formatCount, formatDateTime, formatMoney } from "@/lib/format";

const ROWS: [string, (o: OfferCard) => React.ReactNode][] = [
  ["Платформа", (o) => PLATFORM_LABEL[o.platform]],
  ["Категория", (o) => o.category || "—"],
  ["Подписчики", (o) => (o.followers != null ? formatCount(o.followers) : "—")],
  ["Средние просмотры", (o) => (o.avg_views != null ? `${formatCount(o.avg_views)} (${o.videos_in_sample} видео)` : "—")],
  ["Статистика", (o) => <TrustBadge status={o.trust_status} />],
  ["Обновлена", (o) => (o.stats_updated_at ? formatDateTime(o.stats_updated_at) : "—")],
  ["Цена от", (o) => (o.min_price_minor != null ? formatMoney(o.min_price_minor) : "—")],
  ["Цена за 1000 средних просмотров", (o) => (o.min_price_minor && o.avg_views ? formatMoney(Math.round((o.min_price_minor * 1000) / o.avg_views)) : "—")],
  ["Форматы", (o) => o.formats.join(", ")],
  ["Продавец", (o) => `${o.seller.display_name}${o.seller.rating != null ? ` ★ ${o.seller.rating.toFixed(1)}` : ""}`],
];

export default function ComparePage() {
  const [ids, setIds] = useState<string[]>();
  const [rows, setRows] = useState<OfferCard[]>();
  const [err, setErr] = useState<string>();
  useEffect(() => setIds(getCompareList()), []);
  useEffect(() => {
    if (ids && ids.length >= 2) void compare(ids).then(setRows).catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [ids]);
  if (!ids) return <LoadingState />;
  if (ids.length < 2) return <EmptyState title="Добавьте к сравнению хотя бы два предложения">Кнопка «Добавить к сравнению» есть на странице предложения.</EmptyState>;
  if (err) return <ErrorState message={err} />;
  if (!rows) return <LoadingState />;
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Сравнение предложений</h1>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr><th />{rows.map((o) => (
              <th key={o.id} className="p-2 text-left align-bottom">
                <Link href={`/catalog/${o.id}`} className="text-accent">{o.title}</Link>
                <button className="ml-2 text-xs text-muted" onClick={() => { const n = ids.filter((x) => x !== o.id); setCompareList(n); setIds(n); }}>убрать</button>
              </th>))}</tr>
          </thead>
          <tbody>{ROWS.map(([label, f]) => (
            <tr key={label} className="border-t border-border"><td className="p-2 text-muted">{label}</td>{rows.map((o) => <td key={o.id} className="p-2">{f(o)}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
