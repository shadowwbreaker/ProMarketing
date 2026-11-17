"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { apiFetch } from "@/lib/api/client";
import type { Me } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

export default function SupportRoles() {
  const { me } = useAuth();
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (!me?.permissions.includes("user.manage_roles")) return <p role="alert">Управление ролями доступно главному администратору.</p>;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setResult("");
    setError("");
    try {
      const user = await apiFetch<Me>("/staff/support/roles", { method: "PUT", body: {
        email: form.get("email"), role: form.get("role"), enabled: form.get("action") === "grant",
      } });
      setResult("Права для " + user.email + " обновлены.");
    } catch (ex) {
      const errors = fieldErrors(ex);
      setError(errors.form ?? Object.values(errors.fields)[0] ?? "Не удалось изменить роль.");
    } finally { setBusy(false); }
  }

  return <section className="mx-auto grid w-full max-w-lg gap-4">
    <Link href="/staff/tickets" className="text-sm font-semibold text-accent">К запросам</Link>
    <h1 className="text-2xl font-bold">Роли сотрудников</h1>
    <Link href="/staff/users" className="text-sm font-semibold text-accent">Выбрать пользователя и изменить его роли</Link>
    <Card>
      <form method="post" onSubmit={submit} className="grid gap-4">
        <Field label="Email пользователя" name="email" type="email" required />
        <label className="grid gap-1 text-sm">Роль
          <select name="role" className="rounded-lg border border-border bg-surface px-3 py-2">
            <option value="support_agent">Техническая поддержка</option>
            <option value="admin">Администратор</option>
            <option value="arbitrator">Арбитраж</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm">Действие
          <select name="action" className="rounded-lg border border-border bg-surface px-3 py-2">
            <option value="grant">Назначить</option>
            <option value="revoke">Отозвать</option>
          </select>
        </label>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        {result && <p role="status" className="text-sm text-ok">{result}</p>}
        <Button type="submit" loading={busy}>Сохранить</Button>
      </form>
    </Card>
  </section>;
}
