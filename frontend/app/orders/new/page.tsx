"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { FormError } from "@/components/AuthCard";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { LoadingState } from "@/components/ui/States";
import { createOrder } from "@/lib/api/orders";
import { getNetworkCard, NetworkCard } from "@/lib/api/public";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatMoney } from "@/lib/format";

function NewOrder() {
  const q = useSearchParams();
  const router = useRouter();
  const { me, loading } = useAuth();
  const offer = q.get("offer");
  const networkId = q.get("network");
  const [net, setNet] = useState<NetworkCard>();
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ form?: string; fields: Record<string, string> }>({ fields: {} });

  useEffect(() => {
    if (!loading && !me) router.replace("/login");
  }, [loading, me, router]);
  useEffect(() => {
    if (networkId) void getNetworkCard(networkId).then(setNet);
  }, [networkId]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const terms: Record<string, unknown> = {};
    for (const k of ["brand", "site_url", "brief", "ad_text", "cta", "extra_requirements"]) {
      const v = String(f.get(k) ?? "").trim();
      if (v) terms[k] = v;
    }
    const links = String(f.get("links") ?? "").split(/\s+/).filter(Boolean);
    if (links.length) terms.links = links;
    const pd = String(f.get("publish_deadline") ?? "");
    if (pd) terms.publish_deadline = new Date(pd).toISOString();
    const md = String(f.get("materials_deadline") ?? "");
    if (md) terms.materials_deadline = new Date(md).toISOString();
    setBusy(true);
    setErr({ fields: {} });
    try {
      const body: Record<string, unknown> = { terms, results_report: f.get("results_report") === "on" };
      if (offer) body.offer = offer;
      if (networkId) {
        body.network = networkId;
        if (picked.size && net && picked.size < (net.items?.length ?? 0)) body.network_items = [...picked];
      }
      const o = await createOrder(body);
      router.push(`/orders/${o.id}`);
    } catch (ex) {
      const fe = fieldErrors(ex);
      const termsErr = (fe.fields.terms as unknown as Record<string, string[]>) ?? {};
      setErr({ form: fe.form ?? (Object.keys(termsErr).length ? "Проверьте поля ТЗ" : undefined), fields: Object.fromEntries(Object.entries(termsErr).map(([k, v]) => [k, String(v)])) });
    } finally {
      setBusy(false);
    }
  }

  if (loading || !me) return <LoadingState />;
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold">Оформление заказа</h1>
      <p className="mb-6 text-sm text-muted">
        Все условия фиксируются до оплаты. После оплаты изменить их можно только с согласия продавца. Деньги удерживаются у
        платёжного провайдера и переводятся продавцу через 48 часов после вашего подтверждения.
      </p>
      {!me.is_email_verified && <p role="alert" className="mb-4 rounded-lg bg-warn/10 p-3 text-sm">Подтвердите email, чтобы оформить заказ.</p>}
      {net && (
        <Card className="mb-4">
          <p className="mb-2 font-semibold">Сетка «{net.title}» — {formatMoney(net.stats.price_minor)} за все аккаунты</p>
          {net.allow_partial_purchase && (
            <>
              <p className="mb-2 text-sm text-muted">Можно выбрать отдельные аккаунты (по их цене). Ничего не выбрано — вся сетка.</p>
              <ul className="grid gap-1 text-sm">
                {net.items?.map((i) => (
                  <li key={i.id}>
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={picked.has(i.id)} onChange={(e) => {
                        const s = new Set(picked);
                        if (e.target.checked) s.add(i.id); else s.delete(i.id);
                        setPicked(s);
                      }} />
                      {i.account.title} · {formatMoney(i.price_minor)}
                    </label>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      )}
      <Card>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <FormError message={err.form} />
          <Field label="Бренд или продукт" name="brand" required error={err.fields.brand} />
          <Field label="Сайт" name="site_url" type="url" placeholder="https://" error={err.fields.site_url} />
          <label className="flex flex-col gap-1 text-sm font-medium">Техническое задание
            <textarea name="brief" required rows={5} className="rounded-lg border border-border bg-surface px-3 py-2 font-normal" />
            {err.fields.brief && <span className="text-xs text-danger">{err.fields.brief}</span>}
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">Текст рекламы
            <textarea name="ad_text" rows={3} className="rounded-lg border border-border bg-surface px-3 py-2 font-normal" />
          </label>
          <Field label="Призыв к действию (CTA)" name="cta" />
          <Field label="Ссылки (через пробел)" name="links" />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Опубликовать не позже" name="publish_deadline" type="datetime-local" />
            <Field label="Материалы передам до" name="materials_deadline" type="datetime-local" />
          </div>
          <Field label="Дополнительные требования" name="extra_requirements" />
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" name="results_report" className="mt-1" />
            <span>Получить отчёт по просмотрам рекламы через 24 часа, 7 и 30 дней. Это ровно три разовые проверки публикации через официальный API — без постоянного отслеживания.</span>
          </label>
          <Button type="submit" loading={busy} disabled={!me.is_email_verified}>Создать заказ и перейти к оплате</Button>
        </form>
      </Card>
    </div>
  );
}

export default function NewOrderPage() {
  return <Suspense><NewOrder /></Suspense>;
}
