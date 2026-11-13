"use client";

import { useEffect, useState } from "react";
import { getMeta } from "@/lib/api/meta";

/** D-025: makes it obvious to every visitor that payments in the beta are simulated. */
export function BetaBanner() {
  const [beta, setBeta] = useState(false);
  useEffect(() => void getMeta().then((m) => setBeta(m.beta)), []);
  if (!beta) return null;
  return (
    <div className="bg-text px-4 py-2 text-center text-xs font-medium text-surface">
      Бета-версия ProMarketing · всё работает по-настоящему, кроме оплаты: она имитируется, деньги не списываются
    </div>
  );
}
