"use client";

import Link from "next/link";
import { Avatar } from "@/components/profile/Avatar";
import { Conversation } from "@/components/profile/Conversation";
import { useAuth } from "@/lib/auth/AuthProvider";
import { reviewsWord } from "@/lib/format";

type Props = { userId: string; avatar?: string | null; name: string; online: boolean; rating: number | null; reviews: number };

/** Right-hand panel on a profile or offer page: "write to the seller before paying" (FunPay-style). */
export function DirectChat({ userId, avatar, name, online, rating, reviews }: Props) {
  const { me, loading } = useAuth();
  const own = me?.id === userId;
  const empty = (
    <>
      <p className="text-3xl tracking-[0.2em] text-[#f5c518]" aria-hidden>★★★★★</p>
      <Link href={`/sellers/${userId}#reviews`} className="mt-2 block text-sm font-semibold text-accent hover:underline">
        {rating != null ? `${rating.toFixed(1)} · ` : ""}{reviews} {reviewsWord(reviews)}
      </Link>
      <p className="mt-2 text-sm text-muted">{own ? "Здесь покупатели пишут вам до оплаты" : <>Напишите продавцу<br />перед оплатой</>}</p>
    </>
  );
  return (
    <aside className="flex h-[34rem] flex-col rounded-xl border border-border bg-surface lg:sticky lg:top-4">
      <div className="flex items-center gap-3 border-b border-border px-5 py-4">
        <Link href={`/sellers/${userId}`}><Avatar id={userId} name={name} size={48} src={avatar} /></Link>
        <div className="min-w-0">
          <Link href={`/sellers/${userId}`} className="block truncate font-bold hover:text-accent">{name}</Link>
          <p className={`text-sm font-semibold ${online ? "text-ok" : "text-muted"}`}>{online ? "Онлайн" : "Не в сети"}</p>
        </div>
      </div>
      {loading ? null : me && !own ? (
        <Conversation userId={userId} otherName={name} empty={empty} />
      ) : (
        <div className="flex flex-1 flex-col">
          <div className="m-auto px-5 text-center">{empty}</div>
          <p className="border-t border-border p-4 text-center text-sm">
            {own ? <>Все переписки — в <Link href="/messages" className="font-semibold text-accent">Сообщениях</Link></>
              : <><Link href="/login" className="font-semibold text-accent">Войдите</Link>, чтобы написать продавцу</>}
          </p>
        </div>
      )}
    </aside>
  );
}
