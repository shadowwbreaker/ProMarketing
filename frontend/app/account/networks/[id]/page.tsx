"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { listMine } from "@/lib/api/auth";
import { addNetworkItem, getNetwork, listOffers, Network, Offer, removeNetworkItem, rublesToMinor, updateNetwork } from "@/lib/api/catalog";
import { fieldErrors } from "@/lib/forms";
import { formatCount, formatMoney } from "@/lib/format";

type Acc = { id: string; title: string; handle: string; platform: string };

export default function NetworkPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [net, setNet] = useState<Network>();
  const [offers, setOffers] = useState<(Offer & { accTitle: string })[]>([]);

  const load = useCallback(() => getNetwork(id).then(setNet), [id]);
  useEffect(() => {
    void load();
    void listMine<Acc>("accounts").then(async (p) => {
      const all = await Promise.all(p.results.map(async (a) => (await listOffers(a.id)).filter((o) => o.is_active).map((o) => ({ ...o, accTitle: a.title }))));
      setOffers(all.flat());
    });
  }, [load]);

  if (!net) return <LoadingState />;
  const inNet = new Set(net.items.map((i) => i.social_account));
  const err = (ex: unknown) => toast(fieldErrors(ex).form ?? "Ошибка", "error");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">{net.title}</h1>
        <p className="text-sm text-muted">{net.description}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-4">
        <Card><p className="text-xs text-muted">Аккаунтов</p><p className="text-xl font-bold">{net.stats.accounts}</p></Card>
        <Card><p className="text-xs text-muted">Подписчиков всего</p><p className="text-xl font-bold">{formatCount(net.stats.total_followers)}</p></Card>
        <Card><p className="text-xs text-muted">Сумма средних просмотров</p><p className="text-xl font-bold">{formatCount(net.stats.total_avg_views)}</p></Card>
        <Card><p className="text-xs text-muted">Цена сетки</p><p className="text-xl font-bold">{formatMoney(net.stats.price_minor)}</p>
          <button className="text-xs text-accent" onClick={() => {
            const v = prompt("Цена всей сетки, ₽ (пусто — сумма позиций)", net.total_price_minor ? String(net.total_price_minor / 100) : "");
            if (v === null) return;
            updateNetwork(id, { total_price_minor: v ? rublesToMinor(v) : null }).then(setNet).catch(err);
          }}>изменить</button>
        </Card>
      </div>
      <Card>
        <h2 className="mb-3 font-bold">Аккаунты в сетке</h2>
        <ul className="divide-y divide-border text-sm">
          {net.items.map((i) => (
            <li key={i.id} className="flex justify-between py-2">
              <span>{i.account.title} · {i.account.platform} @{i.account.handle} · {formatMoney(i.price_minor)}</span>
              <button className="text-danger" onClick={() => removeNetworkItem(id, i.id).then(load).catch(err)}>Убрать</button>
            </li>
          ))}
        </ul>
      </Card>
      <Card>
        <h2 className="mb-3 font-bold">Добавить предложение в сетку</h2>
        <ul className="divide-y divide-border text-sm">
          {offers.filter((o) => !inNet.has(o.social_account)).map((o) => (
            <li key={o.id} className="flex items-center justify-between py-2">
              <span>{o.accTitle} · {o.ad_format_label} · {formatMoney(o.price_minor)}</span>
              <Button variant="secondary" onClick={() => addNetworkItem(id, o.id).then(setNet).catch(err)}>Добавить</Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
