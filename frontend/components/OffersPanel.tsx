"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { createOffer, getAdFormats, listOffers, Offer, rublesToMinor, setListing, updateOffer } from "@/lib/api/catalog";
import { fieldErrors } from "@/lib/forms";
import { formatMoney } from "@/lib/format";

export function OffersPanel({ accountId, listed, onChanged }: { accountId: string; listed: boolean; onChanged: () => void }) {
  const toast = useToast();
  const [offers, setOffers] = useState<Offer[]>([]);
  const [formats, setFormats] = useState<{ value: string; label: string }[]>([]);

  const load = useCallback(() => listOffers(accountId).then(setOffers), [accountId]);
  useEffect(() => {
    void load();
    void getAdFormats().then(setFormats);
  }, [load]);

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const form = e.currentTarget;
    try {
      await createOffer(accountId, {
        ad_format: String(f.get("ad_format")),
        price_minor: rublesToMinor(String(f.get("price"))),
        placement_days: Number(f.get("placement_days")),
        publish_within_days: Number(f.get("publish_within_days")),
        conditions: String(f.get("conditions") ?? ""),
      });
      form.reset();
      await load();
      toast("Предложение добавлено", "success");
    } catch (ex) {
      const fe = fieldErrors(ex);
      toast(fe.form ?? Object.values(fe.fields)[0] ?? "Ошибка", "error");
    }
  }

  async function toggleListing() {
    try {
      await setListing(accountId, !listed);
      onChanged();
      toast(listed ? "Снято с каталога" : "Опубликовано в каталоге", "success");
    } catch (ex) {
      toast(fieldErrors(ex).form ?? "Ошибка", "error");
    }
  }

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-bold">Рекламные предложения</h2>
        <Button variant={listed ? "secondary" : "primary"} onClick={toggleListing}>
          {listed ? "Снять с каталога" : "Опубликовать в каталоге"}
        </Button>
      </div>
      <ul className="mb-4 divide-y divide-border text-sm">
        {offers.map((o) => (
          <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span className={o.is_active ? "" : "text-muted line-through"}>
              {o.ad_format_label} · {formatMoney(o.price_minor)} · {o.placement_days} дн. размещения
            </span>
            <span className="flex gap-2">
              <button
                className="text-accent"
                onClick={async () => {
                  const v = prompt("Новая цена, ₽", String(o.price_minor / 100));
                  if (!v) return;
                  try {
                    await updateOffer(o.id, { price_minor: rublesToMinor(v) });
                    await load();
                  } catch (ex) {
                    toast(fieldErrors(ex).form ?? "Ошибка", "error");
                  }
                }}
              >
                Цена
              </button>
              <button
                className="text-muted"
                onClick={() => updateOffer(o.id, { is_active: !o.is_active }).then(load).then(onChanged)}
              >
                {o.is_active ? "Отключить" : "Включить"}
              </button>
            </span>
          </li>
        ))}
        {!offers.length && <li className="py-2 text-muted">Предложений пока нет</li>}
      </ul>
      <form onSubmit={add} className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col text-sm">
          Формат
          <select name="ad_format" className="rounded-lg border border-border bg-surface px-3 py-2">
            {formats.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-sm">Цена, ₽<input name="price" inputMode="decimal" required className="rounded-lg border border-border bg-surface px-3 py-2" /></label>
        <label className="flex flex-col text-sm">Срок размещения, дней<input name="placement_days" type="number" defaultValue={30} min={1} className="rounded-lg border border-border bg-surface px-3 py-2" /></label>
        <label className="flex flex-col text-sm">Опубликовать в течение, дней<input name="publish_within_days" type="number" defaultValue={7} min={1} className="rounded-lg border border-border bg-surface px-3 py-2" /></label>
        <label className="flex flex-col text-sm sm:col-span-2">Условия размещения<textarea name="conditions" rows={2} className="rounded-lg border border-border bg-surface px-3 py-2" /></label>
        <Button type="submit" className="sm:col-span-2">Добавить предложение</Button>
      </form>
    </Card>
  );
}
