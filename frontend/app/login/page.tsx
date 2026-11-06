"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthCard, FormError } from "@/components/AuthCard";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { login } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

export default function LoginPage() {
  const router = useRouter();
  const { setMe } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ form?: string; fields: Record<string, string> }>({ fields: {} });

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setErr({ fields: {} });
    try {
      setMe(await login(String(f.get("email")), String(f.get("password"))));
      router.push("/account");
    } catch (ex) {
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Вход"
      footer={
        <>
          Нет аккаунта? <Link className="font-semibold text-accent" href="/register">Зарегистрироваться</Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormError message={err.form} />
        <Field label="Email" name="email" type="email" autoComplete="email" required error={err.fields.email} />
        <Field label="Пароль" name="password" type="password" autoComplete="current-password" required error={err.fields.password} />
        <Button type="submit" loading={busy}>Войти</Button>
        <Link href="/forgot-password" className="text-center text-sm text-muted hover:text-accent">
          Забыли пароль?
        </Link>
      </form>
    </AuthCard>
  );
}
