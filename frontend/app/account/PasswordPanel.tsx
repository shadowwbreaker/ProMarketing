"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { changePassword } from "@/lib/api/auth";
import { fieldErrors } from "@/lib/forms";

/** Password change: other sessions are signed out by the backend, this one stays. */
export function PasswordPanel() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ form?: string; fields: Record<string, string> }>({ fields: {} });

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const next = String(f.get("new_password"));
    if (next !== String(f.get("repeat"))) return setErr({ fields: { repeat: "Пароли не совпадают" } });
    setBusy(true);
    setErr({ fields: {} });
    try {
      await changePassword(String(f.get("old_password")), next);
      form.reset();
      toast("Пароль изменён. На других устройствах нужно будет войти заново.", "success");
    } catch (ex) {
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="mb-1 text-lg font-bold">Пароль</h2>
      <p className="mb-4 text-sm text-muted">После смены пароля все остальные сеансы будут завершены.</p>
      <form onSubmit={submit} className="flex max-w-md flex-col gap-4" noValidate>
        {err.form && <p role="alert" className="text-sm text-danger">{err.form}</p>}
        <Field label="Текущий пароль" name="old_password" type="password" autoComplete="current-password" required error={err.fields.old_password} />
        <Field label="Новый пароль" name="new_password" type="password" autoComplete="new-password" required minLength={10}
          hint="Не короче 10 символов, не совпадает с email" error={err.fields.new_password} />
        <Field label="Повторите новый пароль" name="repeat" type="password" autoComplete="new-password" required error={err.fields.repeat} />
        <Button type="submit" loading={busy} className="self-start">Сменить пароль</Button>
      </form>
    </Card>
  );
}
