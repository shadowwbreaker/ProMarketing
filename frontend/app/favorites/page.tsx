"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { OfferTable } from "@/components/catalog/OfferTable";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { getFavorites } from "@/lib/api/insights";
import type { NetworkCard, OfferCard } from "@/lib/api/public";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

export default function FavoritesPage() {
  const { me, loading } = useAuth();
  const router = useRouter();
  const [d, setD] = useState<{ accounts: OfferCard[]; networks: NetworkCard[] }>();
  const [err, setErr] = useState<string>();
  useEffect(() => {
    if (!loading && !me) router.replace("/login");
    if (me) getFavorites().then(setD).catch((e) => setErr(fieldErrors(e).form));
  }, [loading, me, router]);
  if (err) return <ErrorState message={err} />;
  if (!d) return <LoadingState />;
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-extrabold tracking-tight">Избранное</h1>
      {d.accounts.length || d.networks.length ? (
        <OfferTable offers={d.accounts} networks={d.networks} />
      ) : (
        <EmptyState title="В избранном пусто">
          <p className="mt-1 text-sm text-muted">Нажимайте «♥ В избранное» на странице канала. <Link href="/catalog" className="text-accent">Перейти в каталог</Link></p>
        </EmptyState>
      )}
    </div>
  );
}
