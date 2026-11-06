"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { EmptyState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { createNetwork, listNetworks, Network } from "@/lib/api/catalog";
import { fieldErrors } from "@/lib/forms";
import { formatCount, formatMoney } from "@/lib/format";

export default function NetworksPage() {
  const toast = useToast();
  const [nets, setNets] = useState<Network[]>();
  const load = () => listNetworks().then(setNets);
  useEffect(() => {
    void load();
  }, []);

  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await createNetwork({ title: String(f.get("title")), description: String(f.get("description") ?? ""), allow_partial_purchase: f.get("partial") === "on" });
      form.reset();
      await load();
    } catch (ex) {
      toast(fieldErrors(ex).form ?? "Ошибка", "error");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Мои рекламные сетки</h1>
      {!nets ? (
        <LoadingState />
      ) : nets.length ? (
        <ul className="grid gap-3 sm:grid-cols-2">
          {nets.map((n) => (
            <li key={n.id}>
              <Link href={`/account/networks/${n.id}`}>
                <Card className="hover:border-accent">
                  <p className="font-semibold">{n.title}</p>
                  <p className="text-sm text-muted">
                    {n.stats.accounts} акк. · {formatCount(n.stats.total_followers)} подписчиков · {formatMoney(n.stats.price_minor)}
                  </p>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="Сеток пока нет">Объедините несколько своих аккаунтов, чтобы продавать рекламу пакетом.</EmptyState>
      )}
      <Card>
        <h2 className="mb-3 font-bold">Новая сетка</h2>
        <form onSubmit={create} className="flex max-w-md flex-col gap-3">
          <Field label="Название" name="title" required />
          <Field label="Описание" name="description" />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="partial" defaultChecked /> Разрешить покупку отдельных аккаунтов</label>
          <Button type="submit">Создать</Button>
        </form>
      </Card>
    </div>
  );
}
