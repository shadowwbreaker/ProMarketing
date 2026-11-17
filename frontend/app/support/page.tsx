"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { EvidencePicker } from "@/components/EvidencePicker";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { LoadingState } from "@/components/ui/States";
import type { Evidence } from "@/lib/api/disputes";
import { complaintUrl, getComplaintOptions, getTopics, submitTicket, type ComplaintOptions } from "@/lib/api/support";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

const input = "rounded-lg border border-border bg-surface px-3 py-2";
const orderNumber = /^#?(?:[a-f0-9]{8}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/i;

function SupportForm() {
  const router = useRouter();
  const initialOrder = useSearchParams().get("order") ?? "";
  const { me, loading } = useAuth();
  const [topics, setTopics] = useState<Record<string, string>>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [topic, setTopic] = useState(initialOrder ? "order" : "");
  const [number, setNumber] = useState(initialOrder);
  const [lookup, setLookup] = useState<{ number: string; options: ComplaintOptions }>();
  const [orderError, setOrderError] = useState("");
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const complaint = topic === "order" || topic === "refund";
  const normalizedNumber = number.trim();
  const validNumber = orderNumber.test(normalizedNumber);
  const options = lookup?.number === normalizedNumber ? lookup.options : undefined;

  async function loadTopics() {
    try { setTopics(await getTopics()); setError(""); }
    catch { setError("Не удалось загрузить темы."); }
  }
  useEffect(() => { if (me) void loadTopics(); }, [me]);
  useEffect(() => {
    setOrderError("");
    setLookup(undefined);
    if (!me || !complaint || !validNumber) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void getComplaintOptions(normalizedNumber, controller.signal).then((result) => {
        if (!controller.signal.aborted) setLookup({ number: normalizedNumber, options: result });
      }).catch((err) => {
        if (!controller.signal.aborted) setOrderError(fieldErrors(err).form ?? "Не удалось найти заказ.");
      });
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [me, complaint, validNumber, normalizedNumber]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const result = await submitTicket({
        category: topic, body: String(f.get("body")), order_number: normalizedNumber,
        ...(complaint && { reason: String(f.get("reason")), items: f.getAll("items").map(String), evidence }),
      });
      router.push(result.kind === "dispute" && result.order ? complaintUrl(result.order, result.id) : "/support/tickets/" + result.id);
    } catch (ex) {
      const errors = fieldErrors(ex);
      setError(errors.form ?? Object.values(errors.fields)[0] ?? "Не удалось отправить обращение.");
    } finally { setBusy(false); }
  }

  return (
    <section className="mx-auto max-w-xl">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Поддержка</h1>
        {me && <Link className="text-sm font-semibold text-accent" href="/support/tickets">Мои обращения</Link>}
      </div>
      <Card>
        {loading ? <LoadingState /> : !me ? (
          <Link className="text-sm font-semibold text-accent" href="/login">Войти, чтобы отправить обращение</Link>
        ) : <>
          {error && <p role="alert" className="mb-3 text-sm text-danger">{error}</p>}
          {topics ? <form method="post" onSubmit={submit} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm font-medium">Тема
              <select name="category" required value={topic} onChange={(event) => setTopic(event.target.value)} className={input}>
                <option value="" disabled>Выберите тему</option>
                {Object.entries(topics).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
              </select>
            </label>
            <Field label="Номер заказа" name="order_number" required={complaint} value={number}
              onChange={(event) => setNumber(event.target.value)}
              placeholder="Например, #4c3daf29" maxLength={37} error={complaint ? orderError || undefined : undefined} />
            {complaint && <>
              <label className="flex flex-col gap-1 text-sm font-medium">Причина
                <select name="reason" required disabled={!options} key={normalizedNumber} defaultValue="" className={input}>
                  <option value="" disabled>{options ? "Выберите причину" : "Сначала укажите номер заказа"}</option>
                  {options?.reasons.map(({ code, title }) => <option key={code} value={code}>{title}</option>)}
                </select>
              </label>
              {options && options.items.length > 1 && (
                <fieldset className="grid gap-1 text-sm" key={normalizedNumber}>
                  <legend>Каналы, которых касается жалоба</legend>
                  <p className="text-xs text-muted">Если ничего не выбрать, жалоба коснётся всех позиций заказа.</p>
                  {options.items.map((item) => <label key={item.id} className="flex items-center gap-2">
                    <input type="checkbox" name="items" value={item.id} /> {item.title}
                  </label>)}
                </fieldset>
              )}
            </>}
            <label className="flex flex-col gap-1 text-sm font-medium">{complaint ? "Опишите проблему" : "Вопрос"}
              <textarea name="body" required minLength={complaint ? 20 : 10} maxLength={10000} rows={5} className={input + " font-normal"} />
            </label>
            {complaint && <EvidencePicker value={evidence} onChange={setEvidence} />}
            <Button type="submit" loading={busy} disabled={complaint && !options}>{complaint ? "Отправить жалобу" : "Отправить"}</Button>
          </form> : error ? <Button type="button" variant="secondary" onClick={() => void loadTopics()}>Повторить</Button> : <LoadingState />}
        </>}
      </Card>
    </section>
  );
}

export default function SupportPage() {
  return <Suspense fallback={<LoadingState />}><SupportForm /></Suspense>;
}
