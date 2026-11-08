"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { MineList } from "./MineList";
import { AnalyticsPanel, FavoritesPanel, RecommendationsPanel, ReferralsPanel, ViewedPanel } from "./InsightsPanels";
import { MessagesPanel } from "./MessagesPanel";
import { PayoutsPanel } from "./PayoutsPanel";
import { TwoFactorPanel } from "./TwoFactorPanel";
import { STATUS_LABEL } from "@/lib/api/orders";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { becomeSeller, resendVerification, updateProfile } from "@/lib/api/auth";
import { readAll } from "@/lib/api/chat";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

type Tab = { key: string; label: string; seller?: boolean };
const GROUPS: { title: string; tabs: Tab[] }[] = [
  { title: "Покупки", tabs: [
    { key: "purchases", label: "Мои покупки" },
    { key: "favorites", label: "Избранное" },
    { key: "viewed", label: "Просмотренные" },
    { key: "recommendations", label: "Рекомендации" },
  ] },
  { title: "Продажи", tabs: [
    { key: "accounts", label: "Мои аккаунты" },
    { key: "sales", label: "Мои продажи", seller: true },
    { key: "networks", label: "Сетки аккаунтов", seller: true },
    { key: "payouts", label: "Выплаты", seller: true },
    { key: "analytics", label: "Аналитика" },
  ] },
  { title: "Общение", tabs: [
    { key: "messages", label: "Сообщения" },
    { key: "notifications", label: "Уведомления" },
    { key: "tickets", label: "Обращения в поддержку" },
  ] },
  { title: "Прочее", tabs: [
    { key: "profile", label: "Настройки профиля" },
    { key: "reviews", label: "Мои отзывы" },
    { key: "referrals", label: "Пригласить друга" },
    { key: "activity", label: "История действий" },
  ] },
];

type OrderBrief = { id: string; status: string; total_minor: number; currency: string; created_at: string; items_count: number };
type AccountBrief = { id: string; platform: string; handle: string; title: string; status: string; is_listed: boolean };
type Simple = { id: string; [k: string]: unknown };

export default function AccountPageWrapper() {
  return <Suspense><AccountPage /></Suspense>;
}

function AccountPage() {
  const qsTab = useSearchParams().get("tab");
  const { me, loading, setMe, signOut } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [tab, setTab] = useState("purchases");
  useEffect(() => {
    if (qsTab) setTab(qsTab);
  }, [qsTab]);
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
    <Link href={`/orders/${o.id}`} className="flex flex-wrap justify-between gap-2 hover:text-accent">
      <span>Заказ от {formatDateTime(o.created_at)} · позиций: {o.items_count}</span>
      <span className="font-semibold">{formatMoney(o.total_minor, o.currency)} · {STATUS_LABEL[o.status] ?? o.status}</span>
    </Link>
  );

  return (
    <div className="grid gap-6 md:grid-cols-[220px_1fr]">
      <nav aria-label="Разделы кабинета" className="flex gap-2 overflow-x-auto md:flex-col md:gap-0">
        <Link href={`/sellers/${me.id}`} className="mb-2 hidden rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:text-accent md:block">
          Мой публичный профиль →
        </Link>
        {GROUPS.map((g) => (
          <div key={g.title} className="flex gap-2 md:mb-3 md:flex-col md:gap-0">
            <p className="hidden px-3 pb-1 pt-2 text-[11px] font-bold uppercase tracking-wider text-muted md:block">{g.title}</p>
            {g.tabs.filter((t) => !t.seller || isSeller).map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                aria-current={tab === t.key ? "page" : undefined}
                className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-left text-sm ${tab === t.key ? "bg-surface font-semibold shadow-sm" : "text-muted hover:text-text"}`}
              >
                {t.label}
              </button>
            ))}
          </div>
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
        {tab === "profile" && <TwoFactorPanel />}
        {tab === "purchases" && <MineList<OrderBrief> path="purchases" empty="Покупок пока нет" render={orderRow} />}
        {tab === "sales" && <MineList<OrderBrief> path="sales" empty="Продаж пока нет" render={orderRow} />}
        {tab === "accounts" && (
          <>
            <Link href="/account/accounts/new" className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink">
              + Добавить аккаунт
            </Link>
            {isSeller && <MineList<AccountBrief>
              path="accounts"
              empty="Аккаунтов пока нет"
              render={(a) => (
                <Link href={`/account/accounts/${a.id}`} className="flex justify-between hover:text-accent">
                  <span>{a.title} · {a.platform} @{a.handle}</span>
                  <span className="text-muted">{a.is_listed ? "в каталоге" : "скрыт"}</span>
                </Link>
              )}
            />}
          </>
        )}
        {tab === "networks" && (
          <>
            <Link href="/account/networks" className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink">
              Управлять сетками
            </Link>
            <MineList<Simple>
              path="networks"
              empty="Сеток пока нет"
              render={(n) => <Link href={`/account/networks/${n.id}`} className="hover:text-accent">{String(n.title)}</Link>}
            />
          </>
        )}
        {tab === "payouts" && <PayoutsPanel />}
        {tab === "messages" && <MessagesPanel />}
        {tab === "favorites" && <FavoritesPanel />}
        {tab === "viewed" && <ViewedPanel />}
        {tab === "recommendations" && <RecommendationsPanel />}
        {tab === "analytics" && <AnalyticsPanel />}
        {tab === "referrals" && <ReferralsPanel />}
        {tab === "reviews" && <MineList<Simple> path="reviews" empty="Отзывов пока нет" render={(r) => `${r.rating}★ ${r.text ?? ""}`} />}
        {tab === "tickets" && <MineList<Simple> path="tickets" empty="Обращений нет" render={(t) => `${t.subject} · ${t.status}`} />}
        {tab === "notifications" && (
          <>
            <button className="self-start text-sm text-accent" onClick={() => readAll().then(() => toast("Все прочитаны", "success"))}>Отметить все прочитанными</button>
            <MineList<Simple>
              path="notifications"
              empty="Уведомлений нет"
              render={(n) => {
                const p = n.payload as Record<string, string> | undefined;
                const inner = <><b className={n.read_at ? "font-normal" : ""}>{String(n.title)}</b> {n.body ? `· ${String(n.body)}` : ""} <span className="text-xs text-muted">{formatDateTime(String(n.created_at))}</span></>;
                const href = p?.order ? `/orders/${p.order}` : p?.sender ? `/sellers/${p.sender}` : null;
                return href ? <Link href={href} className="hover:text-accent">{inner}</Link> : inner;
              }}
            />
          </>
        )}
        {tab === "activity" && (
          <MineList<Simple> path="activity" empty="Действий пока нет" render={(a) => `${formatDateTime(String(a.created_at))} · ${a.action}`} />
        )}
      </section>
    </div>
  );
}
