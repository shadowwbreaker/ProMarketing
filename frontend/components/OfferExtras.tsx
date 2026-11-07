"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { getCompareList, markViewed, setCompareList, toggleFavorite } from "@/lib/api/insights";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

export function OfferExtras({ accountId }: { accountId: string }) {
  const { me } = useAuth();
  const toast = useToast();
  const [inCompare, setInCompare] = useState(false);
  useEffect(() => {
    setInCompare(getCompareList().includes(accountId));
    if (me) void markViewed(accountId).catch(() => {});
  }, [accountId, me]);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {me && (
        <Button variant="secondary" onClick={() => toggleFavorite({ account: accountId })
          .then((r) => toast(r.favorite ? "Добавлено в избранное" : "Убрано из избранного", "success"))
          .catch((e) => toast(fieldErrors(e).form ?? "Ошибка", "error"))}>♥ В избранное</Button>
      )}
      <Button variant="ghost" onClick={() => {
        const list = getCompareList().filter((x) => x !== accountId);
        if (!inCompare) list.push(accountId);
        setCompareList(list);
        setInCompare(!inCompare);
      }}>{inCompare ? "Убрать из сравнения" : "Добавить к сравнению"}</Button>
      <Link href="/compare" className="text-sm text-accent">Сравнение</Link>
    </div>
  );
}
