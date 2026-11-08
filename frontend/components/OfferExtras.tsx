"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { toggleFavorite } from "@/lib/api/insights";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

/** "♥ В избранное" on an offer page (comparison was removed, D-022). */
export function OfferExtras({ accountId }: { accountId: string }) {
  const { me } = useAuth();
  const toast = useToast();
  const [fav, setFav] = useState<boolean>();
  if (!me) return null;
  return (
    <button
      type="button"
      aria-pressed={fav}
      onClick={() => toggleFavorite({ account: accountId })
        .then((r) => { setFav(r.favorite); toast(r.favorite ? "Добавлено в избранное" : "Убрано из избранного", "success"); })
        .catch((e) => toast(fieldErrors(e).form ?? "Ошибка", "error"))}
      className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold transition-[border-color,color] duration-150 hover:border-accent hover:text-accent"
    >
      <span aria-hidden className={`transition-transform duration-200 ${fav ? "scale-110 text-accent" : ""}`}>{fav ? "♥" : "♡"}</span>
      {fav ? "В избранном" : "В избранное"}
    </button>
  );
}
