"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Avatar } from "@/components/profile/Avatar";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { DirectThread, listDirect } from "@/lib/api/direct";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";

/** Pre-order conversations. Order chats live on each order page. */
export function MessagesPanel() {
  const [items, setItems] = useState<DirectThread[]>();
  const [err, setErr] = useState<string>();
  useEffect(() => {
    listDirect().then((r) => setItems(r.results)).catch((e) => setErr(fieldErrors(e).form));
  }, []);
  if (err) return <ErrorState message={err} />;
  if (!items) return <LoadingState />;
  if (!items.length) return <EmptyState title="Сообщений пока нет"><p className="mt-1 text-sm text-muted">Переписка по заказам — на странице заказа.</p></EmptyState>;
  return (
    <Card className="flex flex-col divide-y divide-border p-0">
      {items.map((t) => (
        <Link key={t.user.id} href={`/sellers/${t.user.id}`} className="flex items-center gap-3 p-4 hover:bg-bg">
          <Avatar id={t.user.id} name={t.user.display_name} size={40} />
          <div className="min-w-0 flex-1">
            <p className="flex justify-between gap-2 text-sm">
              <b className="truncate">{t.user.display_name}</b>
              <span className="shrink-0 text-xs text-muted">{formatDateTime(t.last_message_at)}</span>
            </p>
            <p className="truncate text-sm text-muted">{t.last_message}</p>
          </div>
          {t.unread > 0 && <span className="rounded-full bg-accent px-2 text-xs font-bold text-accent-ink">{t.unread}</span>}
        </Link>
      ))}
    </Card>
  );
}
