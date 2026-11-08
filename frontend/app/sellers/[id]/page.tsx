"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { NetworkCard } from "@/components/catalog/Cards";
import { Avatar } from "@/components/profile/Avatar";
import { DirectChat } from "@/components/profile/DirectChat";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { getSeller, OfferCard, SellerPage } from "@/lib/api/public";
import { PLATFORM_LABEL } from "@/lib/api/social";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatCount, formatDateTime, formatMoney, reviewsWord, timeAgo } from "@/lib/format";

const Label = ({ children }: { children: React.ReactNode }) => (
  <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">{children}</p>
);

function RatingBlock({ s }: { s: SellerPage }) {
  const total = s.reviews_count || 1;
  return (
    <div>
      <Label>Рейтинг продавца</Label>
      <div className="flex items-center gap-4">
        <p className="text-5xl font-extrabold leading-none">
          {s.rating != null ? s.rating.toFixed(1).replace(/\.0$/, "") : "—"}
          <span className="ml-1 text-sm font-bold">из 5</span>
        </p>
        <div className="flex flex-col gap-0.5" aria-label="Распределение оценок">
          {(["5", "4", "3", "2", "1"] as const).map((k) => (
            <div key={k} className="flex items-center gap-2 text-[10px] leading-none">
              <span className="w-12 text-right tracking-tighter text-warn">{"★".repeat(Number(k))}</span>
              <span className="h-1 w-24 overflow-hidden rounded bg-border">
                <span className="block h-full bg-warn" style={{ width: `${(s.rating_distribution[k] / total) * 100}%` }} />
              </span>
            </div>
          ))}
        </div>
        <a href="#reviews" className="text-sm font-semibold text-accent hover:underline">
          Всего {s.reviews_count} {reviewsWord(s.reviews_count)}
        </a>
      </div>
    </div>
  );
}

function OffersTable({ title, items }: { title: string; items: OfferCard[] }) {
  return (
    <section className="rounded-xl border border-border bg-surface">
      <h3 className="px-4 pt-4 text-lg font-bold text-accent">{title}</h3>
      <table className="mt-2 w-full text-sm">
        <thead>
          <tr className="border-y border-border text-left text-muted">
            <th className="px-4 py-2 font-medium">Аккаунт</th>
            <th className="hidden px-2 py-2 text-right font-medium sm:table-cell">Подписчики</th>
            <th className="hidden px-2 py-2 text-right font-medium sm:table-cell">Просмотры</th>
            <th className="px-4 py-2 text-right font-medium">Цена</th>
          </tr>
        </thead>
        <tbody>
          {items.map((o) => (
            <tr key={o.id} className="border-b border-border last:border-0 hover:bg-bg">
              <td className="px-4 py-3">
                <Link href={`/catalog/${o.id}`} className="font-semibold hover:text-accent">{o.title}</Link>
                <p className="text-xs text-muted">
                  @{o.handle}
                  <span className="sm:hidden"> · {o.followers != null ? formatCount(o.followers) : "—"} подп.</span>
                </p>
              </td>
              <td className="hidden px-2 py-3 text-right sm:table-cell">{o.followers != null ? formatCount(o.followers) : "—"}</td>
              <td className="hidden px-2 py-3 text-right sm:table-cell">{o.avg_views != null ? formatCount(o.avg_views) : "—"}</td>
              <td className="whitespace-nowrap px-4 py-3 text-right font-bold">
                {o.min_price_minor != null ? `от ${formatMoney(o.min_price_minor, o.currency)}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const [s, setS] = useState<SellerPage>();
  const [err, setErr] = useState<string>();
  useEffect(() => {
    getSeller(id).then(setS).catch((e) => setErr(fieldErrors(e).form));
  }, [id]);
  if (err) return <ErrorState message={err} />;
  if (!s) return <LoadingState />;

  const own = me?.id === s.id;
  const byPlatform = (["tiktok", "youtube", "instagram"] as const)
    .map((p) => ({ p, items: s.accounts.filter((a) => a.platform === p) }))
    .filter((g) => g.items.length);

  return (
    <div className="flex flex-col gap-6">
      <section className="overflow-hidden rounded-xl border border-border bg-surface">
        <div className="h-28 bg-gradient-to-r from-accent via-[#7c4dff] to-[#00a3ff] sm:h-36" style={{ borderBottomLeftRadius: "50% 30%", borderBottomRightRadius: "50% 30%" }} />
        <div className="-mt-14 px-5 pb-6 sm:px-8">
          <div className="rounded-full border-4 border-surface bg-surface" style={{ width: 120 }}>
            <Avatar id={s.id} name={s.display_name} size={112} />
          </div>
          <div className="mt-3 flex flex-wrap items-baseline gap-3">
            <h1 className="break-all text-3xl font-extrabold">{s.display_name}</h1>
            <span className={`text-sm font-semibold ${s.online ? "text-ok" : "text-muted"}`}>
              {s.online ? "Онлайн" : s.last_seen_at ? `был(а) ${timeAgo(s.last_seen_at)}` : "Не в сети"}
            </span>
          </div>
          {s.bio && <p className="mt-2 max-w-2xl text-sm text-muted">{s.bio}</p>}
          {own && (
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <Link href="/account/accounts/new" className="rounded-lg bg-accent px-3 py-1.5 font-semibold text-accent-ink">+ Добавить аккаунт</Link>
              <Link href="/account?tab=profile" className="rounded-lg border border-border px-3 py-1.5 font-semibold">Редактировать профиль</Link>
            </div>
          )}
          <div className="mt-6 flex flex-wrap gap-x-12 gap-y-5">
            <div>
              <Label>Дата регистрации</Label>
              <p className="text-sm">{formatDateTime(s.member_since)}</p>
              <p className="text-sm text-muted">{timeAgo(s.member_since)}</p>
            </div>
            <div>
              <Label>Выполнено заказов</Label>
              <p className="text-3xl font-extrabold">{s.completed_orders}</p>
            </div>
            <RatingBlock s={s} />
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="flex min-w-0 flex-col gap-4">
          <Label>Предложения</Label>
          {byPlatform.length ? (
            byPlatform.map((g) => <OffersTable key={g.p} title={PLATFORM_LABEL[g.p]} items={g.items} />)
          ) : (
            <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">
              {own ? (
                <>У вас пока нет объявлений. <Link href="/account/accounts/new" className="font-semibold text-accent">Добавьте первый аккаунт</Link></>
              ) : "Пока нет активных предложений"}
            </div>
          )}
          {s.networks.length > 0 && (
            <>
              <Label>Сетки аккаунтов</Label>
              <div className="grid gap-3 sm:grid-cols-2">{s.networks.map((n) => <NetworkCard key={n.id} n={n} />)}</div>
            </>
          )}

          <h2 id="reviews" className="mt-4 text-xl font-bold">Отзывы</h2>
          {s.reviews.length ? (
            <ul className="flex flex-col gap-3">
              {s.reviews.map((r) => (
                <li key={r.id} className="rounded-xl border border-border bg-surface p-4">
                  <p className="text-sm font-semibold">
                    <span className="text-warn">{"★".repeat(r.rating)}</span>
                    <span className="text-border">{"★".repeat(5 - r.rating)}</span> · {r.author}
                    <span className="ml-2 text-xs font-normal text-muted">{timeAgo(r.created_at)}</span>
                  </p>
                  {r.text && <p className="mt-1 text-sm">{r.text}</p>}
                  {r.seller_reply && <p className="mt-2 border-l-2 border-border pl-3 text-sm text-muted">Ответ продавца: {r.seller_reply}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Отзывов пока нет</p>
          )}
        </div>
        <DirectChat userId={s.id} name={s.display_name} online={s.online} rating={s.rating} reviews={s.reviews_count} />
      </div>
    </div>
  );
}
