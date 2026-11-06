"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { createTicket } from "@/lib/api/disputes";
import { fieldErrors } from "@/lib/forms";

export default function SupportPage() {
  const toast = useToast();
  const [sent, setSent] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await createTicket({ subject: String(f.get("subject")), body: String(f.get("body")) });
      setSent(true);
    } catch (ex) { toast(fieldErrors(ex).form ?? "Ошибка", "error"); }
  }
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-2 text-2xl font-bold">Поддержка</h1>
      <p className="mb-4 text-sm text-muted">Проблема с конкретным заказом? Откройте заказ и нажмите «Пожаловаться» — так жалоба сразу попадёт в арбитраж вместе с перепиской и условиями.</p>
      <Card>
        {sent ? <p>Обращение отправлено. Ответ появится в кабинете → «Обращения».</p> : (
          <form onSubmit={submit} className="flex flex-col gap-3">
            <Field label="Тема" name="subject" required />
            <label className="flex flex-col gap-1 text-sm font-medium">Вопрос
              <textarea name="body" required minLength={10} rows={5} className="rounded-lg border border-border bg-surface px-3 py-2 font-normal" />
            </label>
            <Button type="submit">Отправить</Button>
          </form>
        )}
      </Card>
    </div>
  );
}
