"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { MineList } from "./MineList";
import { AnalyticsPanel, ReferralsPanel } from "./InsightsPanels";
import { PayoutsPanel } from "./PayoutsPanel";
import { PasswordPanel } from "./PasswordPanel";
import { TwoFactorPanel } from "./TwoFactorPanel";
import { STATUS_LABEL } from "@/lib/api/orders";
import { Avatar } from "@/components/profile/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { becomeSeller, deleteAvatar, resendVerification, updateProfile, uploadAvatar } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

type Tab = { key: string; label: string; seller?: boolean };
const GROUPS: { title: string; tabs: Tab[] }[] = [
  { title: "Продажи", tabs: [
    { key: "accounts", label: "Мои каналы" },
    { key: "sales", label: "Мои продажи", seller: true },
    { key: "networks", label: "Сетки каналов", seller: true },
    { key: "payouts", label: "Выплаты", seller: true },
    { key: "analytics", label: "Аналитика" },
  ] },
  { title: "Общение", tabs: [
    { key: "tickets", label: "Обращения в поддержку" },
  ] },
  { title: "Прочее", tabs: [
    { key: "profile", label: "Настройки профиля" },
    { key: "security", label: "Безопасность" },
    { key: "reviews", label: "Мои отзывы" },
    { key: "referrals", label: "Пригласить друга" },
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
  const { me, loading, setMe, signOut, refresh } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [tab, setTab] = useState("profile");
  useEffect(() => {
    // old links: messages and favorites moved to their own pages in the header
    if (qsTab === "messages") router.replace("/messages");
    else if (qsTab === "favorites") router.replace("/favorites");
    else if (qsTab === "purchases") router.replace("/purchases");
    else if (qsTab) setTab(qsTab);
  }, [qsTab, router]);
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
      setMe(await updateProfile({ bio: String(f.get("bio")) }));
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
              Подтвердите email — без этого нельзя оплачивать заказы и выставлять каналы.{" "}
              <button className="font-semibold underline" onClick={() => resendVerification().then(() => toast("Письмо отправлено", "success"))}>
                Отправить письмо ещё раз
              </button>
            </p>
          </Card>
        )}

        {tab === "profile" && (
          <Card>
            <h2 className="mb-4 text-lg font-bold">Личные данные</h2>
            <div className="mb-5 flex items-center gap-4">
              <Avatar id={me.id} name={me.profile.display_name} size={72} src={me.profile.avatar_url} />
              <div className="flex flex-col gap-1 text-sm">
                <label className="cursor-pointer font-semibold text-accent">
                  {me.profile.avatar_url ? "Заменить фото" : "Загрузить фото"}
                  <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" aria-label="Фото профиля"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      uploadAvatar(f).then(refresh).then(() => toast("Фото обновлено", "success"))
                        .catch((ex) => toast(fieldErrors(ex).form ?? "Не удалось загрузить", "error"));
                    }} />
                </label>
                {me.profile.avatar_url && (
                  <button className="self-start text-muted hover:text-danger" onClick={() => void deleteAvatar().then(refresh)}>Удалить фото</button>
                )}
                <span className="text-xs text-muted">JPG, PNG или WEBP до 5 МБ</span>
              </div>
            </div>
            <p className="mb-4 text-sm text-muted">{me.email} · роли: {me.roles.join(", ")}</p>
            <form onSubmit={saveProfile} className="flex max-w-md flex-col gap-4">
              <div className="flex flex-col gap-1 text-sm">
                <span className="font-medium">Имя пользователя</span>
                <p className="rounded-lg border border-border bg-bg px-3 py-2 font-semibold">{me.profile.display_name}</p>
                <span className="text-xs text-muted">Имя задаётся при регистрации и не меняется — по нему вас узнают покупатели и продавцы.</span>
              </div>
              <label className="flex flex-col gap-1 text-sm font-medium">
                О себе
                <textarea name="bio" defaultValue={me.profile.bio} rows={4} className="rounded-lg border border-border bg-surface px-3 py-2 font-normal" />
              </label>
              <Button type="submit" loading={busy}>Сохранить</Button>
            </form>
            {!isSeller && (
              <div className="mt-6 border-t border-border pt-4">
                <p className="mb-2 text-sm">Хотите продавать рекламу в своих каналах?</p>
                <Button variant="secondary" onClick={() => becomeSeller().then(setMe)}>Стать продавцом</Button>
              </div>
            )}
          </Card>
        )}
        {tab === "security" && <PasswordPanel />}
        {tab === "security" && <TwoFactorPanel />}
        {tab === "sales" && <MineList<OrderBrief> path="sales" empty="Продаж пока нет" render={orderRow} />}
        {tab === "accounts" && (
          <>
            <Link href="/account/accounts/new" className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink">
              + Добавить канал
            </Link>
            {isSeller && <MineList<AccountBrief>
              path="accounts"
              empty="Каналов пока нет"
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
        {tab === "analytics" && <AnalyticsPanel />}
        {tab === "referrals" && <ReferralsPanel />}
        {tab === "reviews" && <MineList<Simple> path="reviews" empty="Отзывов пока нет" render={(r) => `${r.rating}★ ${r.text ?? ""}`} />}
        {tab === "tickets" && <MineList<Simple> path="tickets" empty="Обращений нет" render={(t) => `${t.subject} · ${t.status}`} />}
      </section>
    </div>
  );
}
