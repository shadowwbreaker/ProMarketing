"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { fileUrl } from "@/lib/api/chat";
import { DECISION_LABEL, DISPUTE_STATUS, staffAction, staffDispute } from "@/lib/api/disputes";
import { STATUS_LABEL } from "@/lib/api/orders";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { formatDateTime, formatMoney } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Any = any;

const DECISIONS = ["full_refund", "partial_refund", "reject", "redo", "extend", "in_favor_of_seller"];

export default function StaffDisputePage() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const toast = useToast();
  const [d, setD] = useState<Any>();
  const [err, setErr] = useState<string>();
  const load = useCallback(() => staffDispute(id).then(setD).catch((e) => setErr(fieldErrors(e).form)), [id]);
  useEffect(() => void load(), [load]);

  const act = async (action: string, body: Record<string, unknown> = {}, ok = "Готово") => {
    try {
      setD(await staffAction(id, action, body));
      toast(ok, "success");
    } catch (e) {
      toast(fieldErrors(e).form ?? "Ошибка", "error");
    }
  };

  if (err) return <ErrorState message={err} />;
  if (!d) return <LoadingState />;
  const perms = new Set(me?.permissions ?? []);
  const o = d.order;

  function decide(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const decision = String(f.get("decision"));
    const amount = String(f.get("amount") ?? "");
    const deadline = String(f.get("deadline") ?? "");
    void act("decide", {
      item: f.get("item"), decision, comment: f.get("comment"),
      refund_amount_minor: amount ? Math.round(parseFloat(amount.replace(",", ".")) * 100) : undefined,
      new_deadline: deadline ? new Date(deadline).toISOString() : undefined,
    }, "Решение принято");
  }

  const activeItems = d.items.filter((i: Any) => i.active);
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px] [&>*]:min-w-0">
      <div className="flex flex-col gap-4">
        <div>
          <p className="text-sm text-muted">Спор от {formatDateTime(d.created_at)} · <Link className="text-accent" href={`/orders/${o.id}`}>заказ</Link></p>
          <h1 className="text-2xl font-bold">{d.reason.title} — {DISPUTE_STATUS[d.status]}</h1>
          <p className="text-sm">Открыл: {d.opened_by_role === "buyer" ? "покупатель" : "продавец"}{d.response_overdue && " · сторона не ответила в срок"}{d.has_counterclaim && " · есть встречная претензия"}</p>
        </div>
        <Card><p className="whitespace-pre-line text-sm">{d.description}</p></Card>

        <Card>
          <h2 className="mb-2 font-bold">Стороны</h2>
          {(["buyer", "seller"] as const).map((r) => (
            <p key={r} className="text-sm">
              <b>{r === "buyer" ? "Покупатель" : "Продавец"}:</b> {o[r].name} ({o[r].email}) · споров открыто {o[r].history.opened}, отклонено {o[r].history.rejected}, против него {o[r].history.against}, санкций {o[r].history.sanctions}
              {r === "seller" && o.seller.last_seen_at && ` · был ${formatDateTime(o.seller.last_seen_at)}`}
            </p>
          ))}
        </Card>

        <Card>
          <h2 className="mb-2 font-bold">Позиции и оплата</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-muted"><tr><th>Аккаунт</th><th>Цена</th><th>Статус</th><th>Можно вернуть</th><th>Выплата</th></tr></thead>
            <tbody>
              {o.items.map((it: Any) => (
                <tr key={it.id} className="border-t border-border align-top">
                  <td><a className="text-accent" href={it.account.profile_url} target="_blank" rel="noopener noreferrer nofollow">{it.account.title}</a>
                    {it.proofs.map((p: Any) => <div key={p.id}><a className="break-all text-xs" href={p.video_url} target="_blank" rel="noopener noreferrer nofollow">{p.video_url}</a></div>)}</td>
                  <td>{formatMoney(it.price_minor)}</td><td>{STATUS_LABEL[it.status]}</td>
                  <td>{formatMoney(d.payment.refundable[it.id] ?? 0)}</td><td>{it.payout ? it.payout.status : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">Провайдер: частичный возврат — {d.payment.provider_capabilities.partial_refund ? "да" : "нет"}, возврат до выплаты — {d.payment.provider_capabilities.refund_before_payout ? "да" : "нет"}</p>
        </Card>

        <Card>
          <h2 className="mb-2 font-bold">Условия: исходные (v{o.original_terms.version}) и текущие (v{o.current_terms.version})</h2>
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            {[o.original_terms, o.current_terms].map((t: Any, i: number) => (
              <dl key={i} className="rounded-lg bg-bg p-2"><dt className="text-xs text-muted">ТЗ</dt><dd className="whitespace-pre-line">{t.brief}</dd>
                <dt className="text-xs text-muted">Срок размещения</dt><dd>{t.placement_days} дн.</dd>
                <dt className="text-xs text-muted">Если платформа удалит видео</dt><dd>{t.platform_removal_policy}</dd></dl>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="mb-2 font-bold">Переписка сторон (вся, включая удалённое)</h2>
          <ol className="flex max-h-96 flex-col gap-1 overflow-y-auto text-xs">
            {d.chat.map((m: Any, i: number) => (
              <li key={i} className={m.kind === "system" ? "text-muted" : ""}>
                {formatDateTime(m.created_at)} · {m.kind === "system" ? "система" : m.author === o.buyer.id ? "покупатель" : "продавец"}: {m.body}
                {m.deleted_at && " [удалено]"}{m.revision > 1 && " [изменено]"}{m.contact_signal && " ⚠ контакты"}
                {m.attachments.map((a: string) => <a key={a} className="ml-1 text-accent" href={fileUrl(a)}>📎</a>)}
              </li>
            ))}
          </ol>
        </Card>

        <Card>
          <h2 className="mb-2 font-bold">Сообщения в споре и доказательства</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {d.messages.map((m: Any) => <li key={m.id} className={m.visibility === "staff" ? "rounded bg-warn/10 p-2" : ""}><span className="text-xs text-muted">{formatDateTime(m.created_at)} · {m.author_name}{m.visibility === "staff" && " · только сотрудникам"}</span><p className="whitespace-pre-line">{m.body}</p></li>)}
          </ul>
          <ul className="mt-2 text-xs">
            {d.evidence.map((e: Any) => <li key={e.id}>{formatDateTime(e.created_at)} · {e.submitted_by === o.buyer.id ? "покупатель" : "продавец"}: {e.description} {e.url && <a className="text-accent break-all" href={e.url} target="_blank" rel="noopener noreferrer nofollow">{e.url}</a>} {e.attachment && <a className="text-accent" href={fileUrl(e.attachment)}>файл</a>}</li>)}
          </ul>
        </Card>

        <Card>
          <h2 className="mb-2 font-bold">История заказа и проверки</h2>
          <ol className="grid gap-0.5 text-xs">{d.events.map((e: Any) => <li key={e.seq}>{formatDateTime(e.created_at)} · {e.type}{e.to_status && ` → ${e.to_status}`}</li>)}</ol>
          <p className="mt-2 text-xs">Проверки публикаций: {d.publication_checks.map((c: Any) => `${c.trigger}: ${c.result}`).join("; ") || "нет"}</p>
          {d.account_stats.map((s: Any) => <p key={s.item} className="text-xs">Статистика аккаунта: {s.history.map((h: Any) => `${h.followers}/${h.avg_views ?? "—"} (${h.trust_status})`).join(" → ")}</p>)}
        </Card>
      </div>

      <aside className="flex flex-col gap-3">
        <Card className="flex flex-col gap-2">
          <h2 className="font-bold">Действия</h2>
          <Button variant="secondary" onClick={() => act("assign", {}, "Назначено на вас")}>Взять в работу</Button>
          <Button variant="secondary" onClick={() => act("priority", { priority: d.priority === "high" ? "normal" : "high" })}>Приоритет: {d.priority === "high" ? "высокий" : "обычный"}</Button>
          <Button variant="secondary" onClick={() => {
            const from = prompt("У кого запросить: buyer / seller / both", "seller");
            const comment = from && prompt("Что нужно предоставить?");
            if (from && comment) void act("request-evidence", { from, comment }, "Запрос отправлен");
          }}>Запросить доказательства</Button>
          <Button variant="secondary" onClick={() => { const c = prompt("Причина эскалации"); if (c) void act("escalate", { comment: c }); }}>Передать старшему</Button>
          {activeItems.map((i: Any) => (
            <div key={i.order_item} className="flex gap-1">
              <Button variant="ghost" onClick={() => act("check-publication", { item: i.order_item }, "Проверка публикации запущена")}>Проверить видео</Button>
              <Button variant="ghost" onClick={() => act("check-account", { item: i.order_item }, "Проверка аккаунта запущена")}>Проверить аккаунт</Button>
            </div>
          ))}
        </Card>

        <Card>
          <h2 className="mb-2 font-bold">Сообщение сторонам / заметка</h2>
          <form className="flex flex-col gap-2" onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const form = e.currentTarget;
            void act("message", { body: f.get("body"), internal: f.get("internal") === "on" }, "Отправлено").then(() => form.reset());
          }}>
            <textarea name="body" required rows={3} aria-label="Сообщение администрации" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" />
            <label className="text-xs"><input type="checkbox" name="internal" /> Только для сотрудников</label>
            <Button type="submit" variant="secondary">Отправить</Button>
          </form>
        </Card>

        {perms.has("dispute.decide") && activeItems.length > 0 && (
          <Card>
            <h2 className="mb-2 font-bold">Решение</h2>
            <form onSubmit={decide} className="flex flex-col gap-2 text-sm">
              <label className="flex flex-col">Позиция
                <select name="item" className="rounded-lg border border-border bg-surface px-2 py-1">
                  {activeItems.map((i: Any) => <option key={i.order_item} value={i.order_item}>{i.account} · {formatMoney(i.price_minor)}</option>)}
                </select>
              </label>
              <label className="flex flex-col">Решение
                <select name="decision" className="rounded-lg border border-border bg-surface px-2 py-1">
                  {DECISIONS.filter((x) => perms.has("finance.refund") || !x.includes("refund")).map((x) => <option key={x} value={x}>{DECISION_LABEL[x]}</option>)}
                </select>
              </label>
              <label className="flex flex-col">Сумма частичного возврата, ₽<input name="amount" inputMode="decimal" className="rounded-lg border border-border bg-surface px-2 py-1" /></label>
              <label className="flex flex-col">Новый срок (повтор / продление)<input name="deadline" type="datetime-local" className="rounded-lg border border-border bg-surface px-2 py-1" /></label>
              <label className="flex flex-col">Комментарий (обязательно)<textarea name="comment" required minLength={10} rows={3} className="rounded-lg border border-border bg-surface px-2 py-1" /></label>
              <Button type="submit">Принять решение</Button>
            </form>
          </Card>
        )}

        {perms.has("user.sanction") && (
          <Card>
            <h2 className="mb-2 font-bold">Санкции</h2>
            <form className="flex flex-col gap-2 text-sm" onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void act("decide", { decision: "sanction", comment: f.get("comment"), sanction: { target: f.get("target"), type: f.get("type"), days: f.get("days") || undefined } }, "Санкция применена");
            }}>
              <select name="target" className="rounded-lg border border-border bg-surface px-2 py-1"><option value="seller">Продавцу</option><option value="buyer">Покупателю</option></select>
              <select name="type" className="rounded-lg border border-border bg-surface px-2 py-1"><option value="warning">Предупреждение</option><option value="limit">Ограничение</option><option value="block">Блокировка</option></select>
              <input name="days" type="number" min={1} placeholder="дней (пусто — бессрочно)" className="rounded-lg border border-border bg-surface px-2 py-1" />
              <textarea name="comment" required minLength={10} placeholder="Основание" rows={2} className="rounded-lg border border-border bg-surface px-2 py-1" />
              <Button type="submit" variant="danger">Применить</Button>
            </form>
          </Card>
        )}

        <Card>
          <h2 className="mb-2 font-bold">Внутренние заметки</h2>
          <ul className="text-xs">{d.admin_notes.map((n: Any) => <li key={n.id}>{formatDateTime(n.created_at)}: {n.body}</li>)}</ul>
          <button className="mt-1 text-xs text-accent" onClick={() => { const b = prompt("Заметка"); if (b) void act("note", { body: b }); }}>Добавить заметку</button>
        </Card>

        {d.decisions.length > 0 && (
          <Card>
            <h2 className="mb-2 font-bold">Принятые решения</h2>
            <ul className="text-xs">{d.decisions.map((x: Any) => <li key={x.id}>{DECISION_LABEL[x.type]}: {x.comment}{x.actions.map((a: Any) => ` [${a.status}${a.error ? `: ${a.error}` : ""}]`)}</li>)}</ul>
          </Card>
        )}
      </aside>
    </div>
  );
}
