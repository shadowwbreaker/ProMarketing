"use client";

import { FormEvent, useState } from "react";
import { AuthCard, FormError } from "@/components/AuthCard";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { requestPasswordReset } from "@/lib/api/auth";
import { fieldErrors } from "@/lib/forms";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>();

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      await requestPasswordReset(String(new FormData(e.currentTarget).get("email")));
      setSent(true);
    } catch (ex) {
      setErr(fieldErrors(ex).form);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Восстановление пароля">
      {sent ? (
        <p className="text-sm">Если аккаунт с таким email существует, мы отправили на него ссылку для сброса пароля.</p>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <FormError message={err} />
          <Field label="Email" name="email" type="email" required />
          <Button type="submit" loading={busy}>Отправить ссылку</Button>
        </form>
      )}
    </AuthCard>
  );
}
