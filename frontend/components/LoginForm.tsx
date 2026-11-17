"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthCard, FormError } from "@/components/AuthCard";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { login } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

export function LoginForm({ staffSupport = false }: { staffSupport?: boolean }) {
  const router = useRouter();
  const { setMe } = useAuth();
  const [busy, setBusy] = useState(false);
  const [needOtp, setNeedOtp] = useState(false);
  const [err, setErr] = useState<{ form?: string; fields: Record<string, string> }>({ fields: {} });

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setErr({ fields: {} });
    try {
      const user = await login(String(f.get("email")), String(f.get("password")), f.get("otp") ? String(f.get("otp")) : undefined, staffSupport);
      setMe(user);
      router.push(staffSupport ? (user.permissions.includes("support.work") ? "/staff/tickets" : "/staff/orders") : "/account");
    } catch (ex) {
      if (ex instanceof ApiError && ex.code === "otp_required") setNeedOtp(true);
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title={staffSupport ? "Вход в техническую поддержку" : "Вход"}
      footer={staffSupport ? <Link href="/login" className="text-accent">Вход для пользователей</Link> : (
        <>
          Нет аккаунта? <Link className="font-semibold text-accent" href="/register">Зарегистрироваться</Link>
        </>
      )}
    >
      <form method="post" onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormError message={err.form} />
        <Field label="Email" name="email" type="email" autoComplete="email" required error={err.fields.email} />
        <Field label="Пароль" name="password" type="password" autoComplete="current-password" required error={err.fields.password} />
        {needOtp && <Field label="Код из приложения" name="otp" inputMode="numeric" autoComplete="one-time-code" required />}
        <Button type="submit" loading={busy}>Войти</Button>
        <Link href="/forgot-password" className="text-center text-sm text-muted hover:text-accent">
          Забыли пароль?
        </Link>
      </form>
    </AuthCard>
  );
}
