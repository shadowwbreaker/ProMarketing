"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { MineList } from "./MineList";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { becomeSeller, resendVerification, updateProfile } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

type Tab = { key: string; label: string; seller?: boolean };
const TABS: Tab[] = [
  { key: "profile", label: "Профиль" },
  { key: "purchases", label: "Мои покупки" },
  { key: "sales", label: "Мои продажи", seller: true },
  { key: "accounts", label: "Мои аккаунты", seller: true },
  { key: "networks", label: "Мои сетки", seller: true },
  { key: "reviews", label: "Отзывы" },
  { key: "tickets", label: "Обращения" },
  { key: "notifications", label: "Уведомления" },
  { key: "activity", label: "История действий" },
];

type OrderBrief = { id: string; status: string; total_minor: number; currency: string; created_at: string; items_count: number };
type AccountBrief = { id: string; platform: string; handle: string; title: string; status: string; is_listed: boolean };
type Simple = { id: string; [k: string]: unknown };

export default function AccountPage() {
  const { me, loading, setMe, signOut } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [tab, setTab] = useState("profile");
  const [busy, setBusy] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (!loading && !me && !leaving) router.replace("/login");
  }, [loading, me, leaving, router]);

  if (loading || !me) return <LoadingState />;
  const isSeller = me.roles.includes("seller");

  async function saveProfile(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      setMe(await updateProfile({ display_name: String(f.get("display_name")), bio: String(f.get("bio")) }));
      toast("Профиль сохранён", "success");
    } catch (ex) {
      toast(fieldErrors(ex).form ?? "Проверьте поля", "error");
    } finally {
      setBusy(false);
    }
  }

  const orderRow = (o: OrderBrief) => (
    <div className="flex flex-wrap justify-between gap-2">
      <span>Заказ от {formatDateTime(o.created_at)} · позиций: {o.items_count}</span>
      <span className="font-semibold">{formatMoney(o.total_minor, o.currency)} · {o.status}</span>
    </div>
  );

  return (
    <div className="grid gap-6 md:grid-cols-[220px_1fr]">
      <nav aria-label="Разделы кабинета" className="flex gap-2 overflow-x-auto md:flex-col">
        {TABS.filter((t) => !t.seller || isSeller).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            aria-current={tab === t.key ? "page" : undefined}
            className={`whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm ${tab === t.key ? "bg-surface font-semibold shadow-sm" : "text-muted hover:text-text"}`}
          >
            {t.label}
          </button>
        ))}
        <button
          onClick={() => {
            setLeaving(true);
            void signOut().then(() => router.replace("/"));
          }} className="rounded-lg px-3 py-2 text-left text-sm text-danger">
          Выйти
        </button>
      </nav>

      <section className="flex flex-col gap-4">
        {!me.is_email_verified && (
          <Card className="border-warn/50">
            <p className="text-sm">
              Подтвердите email — без этого нельзя оплачивать заказы и выставлять аккаунты.{" "}
              <button className="font-semibold underline" onClick={() => resendVerification().then(() => toast("Письмо отправлено", "success"))}>
                Отправить письмо ещё раз
              </button>
            </p>
          </Card>
        )}

        {tab === "profile" && (
          <Card>
            <h2 className="mb-4 text-lg font-bold">Личные данные</h2>
            <p className="mb-4 text-sm text-muted">{me.email} · роли: {me.roles.join(", ")}</p>
            <form onSubmit={saveProfile} className="flex max-w-md flex-col gap-4">
              <Field label="Имя или название" name="display_name" defaultValue={me.profile.display_name} required />
              <label className="flex flex-col gap-1 text-sm font-medium">
                О себе
                <textarea name="bio" defaultValue={me.profile.bio} rows={4} className="rounded-lg border border-border bg-surface px-3 py-2 font-normal" />
              </label>
              <Button type="submit" loading={busy}>Сохранить</Button>
            </form>
            {!isSeller && (
              <div className="mt-6 border-t border-border pt-4">
                <p className="mb-2 text-sm">Хотите продавать рекламу в своих аккаунтах?</p>
                <Button variant="secondary" onClick={() => becomeSeller().then(setMe)}>Стать продавцом</Button>
              </div>
            )}
          </Card>
        )}
        {tab === "purchases" && <MineList<OrderBrief> path="purchases" empty="Покупок пока нет" render={orderRow} />}
        {tab === "sales" && <MineList<OrderBrief> path="sales" empty="Продаж пока нет" render={orderRow} />}
        {tab === "accounts" && (
          <>
            <Link href="/account/accounts/new" className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink">
              Добавить аккаунт
            </Link>
            <MineList<AccountBrief>
              path="accounts"
              empty="Аккаунтов пока нет"
              render={(a) => (
                <Link href={`/account/accounts/${a.id}`} className="flex justify-between hover:text-accent">
                  <span>{a.title} · {a.platform} @{a.handle}</span>
                  <span className="text-muted">{a.is_listed ? "в каталоге" : "скрыт"}</span>
                </Link>
              )}
            />
          </>
        )}
        {tab === "networks" && <MineList<Simple> path="networks" empty="Сеток пока нет" render={(n) => String(n.title)} />}
        {tab === "reviews" && <MineList<Simple> path="reviews" empty="Отзывов пока нет" render={(r) => `${r.rating}★ ${r.text ?? ""}`} />}
        {tab === "tickets" && <MineList<Simple> path="tickets" empty="Обращений нет" render={(t) => `${t.subject} · ${t.status}`} />}
        {tab === "notifications" && <MineList<Simple> path="notifications" empty="Уведомлений нет" render={(n) => String(n.title)} />}
        {tab === "activity" && (
          <MineList<Simple> path="activity" empty="Действий пока нет" render={(a) => `${formatDateTime(String(a.created_at))} · ${a.action}`} />
        )}
      </section>
    </div>
  );
}
