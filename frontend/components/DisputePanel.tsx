"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { EvidencePicker } from "@/components/EvidencePicker";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { appealDispute, DECISION_LABEL, Dispute, DISPUTE_STATUS, Evidence, orderDisputes, replyDispute } from "@/lib/api/disputes";
import type { Order } from "@/lib/api/orders";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

function DisputeCard({ d, onChange }: { d: Dispute; onChange: () => void }) {
  const toast = useToast();
  const [ev, setEv] = useState<Evidence[]>([]);
  async function reply(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    try {
      await replyDispute(d.id, String(new FormData(form).get("body") ?? ""), ev);
      form.reset();
      setEv([]);
      onChange();
    } catch (ex) { toast(fieldErrors(ex).form ?? "Ошибка", "error"); }
  }
  const active = !["RESOLVED", "REJECTED", "CLOSED"].includes(d.status);
  return (
    <Card id={"dispute-" + d.id} className="scroll-mt-24 flex flex-col gap-3 border-danger/40">
      <div className="flex flex-wrap justify-between gap-2">
        <p className="font-bold">Жалоба: {d.reason.title}{d.appeal_of && " (апелляция)"}</p>
        <span className="text-sm font-semibold">{DISPUTE_STATUS[d.status] ?? d.status}</span>
      </div>
      <p className="whitespace-pre-line text-sm">{d.description}</p>
      <p className="text-xs text-muted">Позиции: {d.items.map((i) => `${i.account} (${formatMoney(i.price_minor)})`).join(", ")}</p>
      {d.response_due_at && <p className="text-xs text-warn">Ответ ожидается до {formatDateTime(d.response_due_at)}</p>}
      {d.has_counterclaim && <p className="text-xs">Есть встречная претензия — администрация рассмотрит обе стороны.</p>}
      <ul className="flex flex-col gap-2 text-sm">
        {d.messages.map((m) => (
          <li key={m.id} className={`rounded-lg px-3 py-2 ${m.is_staff ? "bg-warn/10" : "bg-bg"}`}>
            <p className="text-[11px] text-muted">{m.is_staff ? "Администрация" : m.author_name} · {formatDateTime(m.created_at)}</p>
            <p className="whitespace-pre-line">{m.body}</p>
          </li>
        ))}
      </ul>
      {d.evidence.length > 0 && <p className="text-xs text-muted">Доказательств приложено: {d.evidence.length}</p>}
      {d.decisions.filter((x) => x.type !== "request_evidence").map((x) => (
        <p key={x.id} className="rounded-lg bg-ok/10 p-2 text-sm"><b>{DECISION_LABEL[x.type]}</b>{x.refund_amount_minor ? ` · ${formatMoney(x.refund_amount_minor)}` : ""}: {x.comment}</p>
      ))}
      {active && (
        <form method="post" onSubmit={reply} className="flex flex-col gap-2">
          <textarea name="body" rows={2} aria-label="Ответ по жалобе" placeholder="Ваш ответ и пояснения" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
          <EvidencePicker value={ev} onChange={setEv} />
          <Button type="submit" variant="secondary">Отправить ответ</Button>
        </form>
      )}
      {(d.status === "RESOLVED" || d.status === "REJECTED") && !d.appeal_of && (
        <Button variant="ghost" onClick={() => {
          const reason = prompt("Почему вы не согласны с решением? (апелляция подаётся один раз, в течение 7 дней)");
          if (reason) appealDispute(d.id, reason).then(onChange).catch((ex) => toast(fieldErrors(ex).form ?? "Ошибка", "error"));
        }}>Обжаловать решение</Button>
      )}
    </Card>
  );
}

export function DisputePanel({ order, onChanged }: { order: Order; onChanged: () => void }) {
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const load = useCallback(() => orderDisputes(order.id).then(setDisputes).catch(() => {}), [order.id]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (disputes.length && window.location.hash.startsWith("#dispute-")) {
      document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
    }
  }, [disputes.length]);

  return (
    <>
      {disputes.map((d) => <DisputeCard key={d.id} d={d} onChange={() => { void load(); onChanged(); }} />)}
      {order.role !== "staff" && order.paid_at && (
        <Link className="self-start rounded-lg bg-danger px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          href={"/support?order=" + order.id}>Пожаловаться</Link>
      )}
    </>
  );
}
