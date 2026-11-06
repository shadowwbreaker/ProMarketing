"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { FormError } from "@/components/AuthCard";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { ApiError } from "@/lib/api/client";
import { createSocialAccount, startTikTokOAuth } from "@/lib/api/social";
import { fieldErrors } from "@/lib/forms";

export default function NewAccountPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ form?: string; fields: Record<string, string> }>({ fields: {} });
  const [oauthNeeded, setOauthNeeded] = useState(false);
  const [manualAllowed, setManualAllowed] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setErr({ fields: {} });
    try {
      const acc = await createSocialAccount({
        profile_url: String(f.get("profile_url")),
        title: String(f.get("title") ?? ""),
        category: String(f.get("category") ?? ""),
        geo: String(f.get("geo") ?? ""),
        description: String(f.get("description") ?? ""),
        manual: f.get("manual") === "on",
      });
      router.push(`/account/accounts/${acc.id}`);
    } catch (ex) {
      if (ex instanceof ApiError && ex.code === "oauth_required") setOauthNeeded(true);
      if (ex instanceof ApiError && ex.details?.manual_allowed) setManualAllowed(true);
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  async function connectTikTok() {
    try {
      const { authorize_url } = await startTikTokOAuth();
      window.location.href = authorize_url;
    } catch (ex) {
      setErr(fieldErrors(ex));
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-2 text-2xl font-bold">Добавить аккаунт</h1>
      <p className="mb-6 text-sm text-muted">
        Статистика собирается один раз при добавлении и затем только по кнопке «Обновить статистику». Постоянного
        мониторинга нет. TikTok подключается через вход в TikTok — так подтверждается, что аккаунт ваш.
      </p>
      <Card className="mb-4">
        <p className="mb-3 text-sm font-semibold">TikTok</p>
        <Button variant="secondary" onClick={connectTikTok}>Подключить через вход в TikTok</Button>
      </Card>
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <FormError message={err.form} />
          {oauthNeeded && <p className="text-sm">Для этой платформы используйте кнопку подключения выше.</p>}
          <Field label="Ссылка на профиль" name="profile_url" placeholder="https://www.youtube.com/@channel" required error={err.fields.profile_url} />
          <Field label="Название" name="title" error={err.fields.title} />
          <Field label="Категория контента" name="category" placeholder="например, лайфстайл" />
          <Field label="География аудитории" name="geo" placeholder="Россия" />
          <label className="flex flex-col gap-1 text-sm font-medium">
            Описание
            <textarea name="description" rows={3} className="rounded-lg border border-border bg-surface px-3 py-2 font-normal" />
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" name="manual" className="mt-1" defaultChecked={false} />
            <span>
              Ввести статистику вручную. Она будет помечена как «Вручную» и не попадёт в фильтр «подтверждённая статистика».
              {manualAllowed && <b> Автоматически получить данные не удалось — можно добавить вручную.</b>}
            </span>
          </label>
          <Button type="submit" loading={busy}>Добавить</Button>
        </form>
      </Card>
    </div>
  );
}
