"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthCard, FormError } from "@/components/AuthCard";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { register } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

export default function RegisterPage() {
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
      const me = await register({
        email: String(f.get("email")),
        password: String(f.get("password")),
        display_name: String(f.get("display_name")),
        as_seller: f.get("as_seller") === "on",
        accept_terms: f.get("accept_terms") === "on",
        ref: new URLSearchParams(window.location.search).get("ref") ?? undefined,
      } as Parameters<typeof register>[0]);
      setMe(me);
      router.push("/account");
    } catch (ex) {
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Регистрация"
      footer={
        <>
          Уже есть аккаунт? <Link className="font-semibold text-accent" href="/login">Войти</Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormError message={err.form} />
        <Field label="Имя или название" name="display_name" required error={err.fields.display_name} />
        <Field label="Email" name="email" type="email" autoComplete="email" required error={err.fields.email} />
        <Field
          label="Пароль"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          hint="Не короче 10 символов, не только цифры"
          error={err.fields.password}
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="as_seller" /> Я хочу продавать рекламу в своих аккаунтах
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" name="accept_terms" required className="mt-1" />
          <span>Принимаю пользовательское соглашение и правила разрешения споров</span>
        </label>
        {err.fields.accept_terms && <p className="text-xs text-danger">{err.fields.accept_terms}</p>}
        <Button type="submit" loading={busy}>Создать аккаунт</Button>
      </form>
    </AuthCard>
  );
}
