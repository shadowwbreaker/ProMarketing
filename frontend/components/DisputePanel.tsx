"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { uploadFile } from "@/lib/api/chat";
import { appealDispute, DECISION_LABEL, Dispute, DISPUTE_STATUS, Evidence, getReasons, openDispute, orderDisputes, Reason, replyDispute } from "@/lib/api/disputes";
import type { Order } from "@/lib/api/orders";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

function EvidencePicker({ value, onChange }: { value: Evidence[]; onChange: (e: Evidence[]) => void }) {
  const toast = useToast();
  return (
    <div className="flex flex-col gap-1 text-xs">
      <label className="cursor-pointer text-accent">
        + Скриншот, видео или PDF
        <input type="file" className="hidden" accept="image/*,application/pdf,video/mp4" onChange={async (e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          try {
            const up = await uploadFile(f);
            onChange([...value, { attachment: up.id, description: up.name }]);
          } catch (ex) { toast(fieldErrors(ex).form ?? "Ошибка загрузки", "error"); }
        }} />
      </label>
      <button type="button" className="self-start text-accent" onClick={() => {
        const url = prompt("Ссылка-доказательство");
        if (url) onChange([...value, { url, description: "ссылка" }]);
      }}>+ Ссылка</button>
      {value.map((e, i) => <span key={i} className="text-muted">📎 {e.description || e.url}</span>)}
    </div>
  );
}

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
    <Card className="flex flex-col gap-3 border-danger/40">
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
        <form onSubmit={reply} className="flex flex-col gap-2">
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
  const toast = useToast();
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [reasons, setReasons] = useState<Reason[]>([]);
  const [open, setOpen] = useState(false);
  const [ev, setEv] = useState<Evidence[]>([]);
  const [items, setItems] = useState<Set<string>>(new Set());
  const load = useCallback(() => orderDisputes(order.id).then(setDisputes).catch(() => {}), [order.id]);
  useEffect(() => {
    void load();
    void getReasons().then(setReasons);
  }, [load]);
  if (order.role === "staff" || !order.paid_at) return <>{disputes.map((d) => <DisputeCard key={d.id} d={d} onChange={load} />)}</>;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await openDispute(order.id, { reason: String(f.get("reason")), description: String(f.get("description") ?? ""), items: [...items], evidence: ev });
      toast("Жалоба отправлена. Другая сторона получит уведомление.", "success");
      setOpen(false);
      setEv([]);
      await load();
      onChanged();
    } catch (ex) { toast(fieldErrors(ex).form ?? "Ошибка", "error"); }
  }

  const mine = reasons.filter((r) => r.allowed_for === order.role || r.allowed_for === "both");
  return (
    <>
      {disputes.map((d) => <DisputeCard key={d.id} d={d} onChange={() => { void load(); onChanged(); }} />)}
      {!open ? (
        <Button variant="danger" className="self-start" onClick={() => setOpen(true)}>Пожаловаться</Button>
      ) : (
        <Card>
          <h2 className="mb-1 font-bold">Жалоба по заказу</h2>
          <p className="mb-3 text-xs text-muted">Деньги не возвращаются автоматически: другая сторона сможет ответить, а решение примет администрация по фактам и доказательствам.</p>
          <form onSubmit={submit} className="flex flex-col gap-3">
            <label className="flex flex-col text-sm">Причина
              <select name="reason" required className="rounded-lg border border-border bg-surface px-3 py-2">
                {mine.map((r) => <option key={r.code} value={r.code}>{r.title}</option>)}
              </select>
            </label>
            {order.items.length > 1 && (
              <fieldset className="text-sm"><legend>Каких аккаунтов касается (ничего не выбрано — всех)</legend>
                {order.items.map((i) => (
                  <label key={i.id} className="flex items-center gap-2"><input type="checkbox" onChange={(e) => {
                    const s = new Set(items);
                    if (e.target.checked) s.add(i.id); else s.delete(i.id);
                    setItems(s);
                  }} /> {i.account.title}</label>
                ))}
              </fieldset>
            )}
            <label className="flex flex-col text-sm">Опишите проблему
              <textarea name="description" required minLength={20} rows={4} className="rounded-lg border border-border bg-surface px-3 py-2" />
            </label>
            <EvidencePicker value={ev} onChange={setEv} />
            <div className="flex gap-2">
              <Button type="submit" variant="danger">Отправить жалобу</Button>
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            </div>
          </form>
        </Card>
      )}
    </>
  );
}
