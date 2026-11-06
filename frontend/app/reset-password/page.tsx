"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { AuthCard, FormError } from "@/components/AuthCard";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { confirmPasswordReset } from "@/lib/api/auth";
import { fieldErrors } from "@/lib/forms";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ form?: string; fields: Record<string, string> }>({ fields: {} });

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      await confirmPasswordReset(token, String(new FormData(e.currentTarget).get("new_password")));
      setDone(true);
    } catch (ex) {
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  if (done)
    return (
      <p className="text-sm">
        Пароль изменён. <Link href="/login" className="font-semibold text-accent">Войти</Link>
      </p>
    );
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <FormError message={err.form} />
      <Field label="Новый пароль" name="new_password" type="password" autoComplete="new-password" required error={err.fields.new_password} />
      <Button type="submit" loading={busy} disabled={!token}>Сохранить пароль</Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthCard title="Новый пароль">
      <Suspense>
        <ResetForm />
      </Suspense>
    </AuthCard>
  );
}
