"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { confirm2fa, disable2fa, get2fa, setup2fa } from "@/lib/api/auth";
import { fieldErrors } from "@/lib/forms";

export function TwoFactorPanel() {
  const toast = useToast();
  const [state, setState] = useState<{ enabled: boolean; required: boolean }>();
  const [setup, setSetup] = useState<{ secret: string; otpauth_url: string }>();
  useEffect(() => void get2fa().then(setState).catch(() => {}), []);
  if (!state) return null;
  const err = (e: unknown) => toast(fieldErrors(e).form ?? "Ошибка", "error");

  async function confirm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      setState({ ...state!, ...(await confirm2fa(String(new FormData(e.currentTarget).get("code")))) });
      setSetup(undefined);
      toast("Двухфакторная защита включена", "success");
    } catch (ex) { err(ex); }
  }

  return (
    <Card>
      <h2 className="mb-1 font-bold">Двухфакторная защита</h2>
      <p className="mb-3 text-sm text-muted">
        {state.enabled ? "Включена: при входе нужен код из приложения-аутентификатора." : state.required ? "Обязательна для служебного раздела." : "Дополнительная защита входа кодом из приложения (Google Authenticator, Яндекс Ключ и др.)."}
      </p>
      {!state.enabled && !setup && <Button variant="secondary" onClick={() => setup2fa().then(setSetup).catch(err)}>Включить</Button>}
      {setup && (
        <form onSubmit={confirm} className="flex flex-col gap-2 text-sm">
          <p>Добавьте в приложение ключ вручную: <code className="break-all font-mono">{setup.secret}</code></p>
          <a className="text-accent" href={setup.otpauth_url}>Открыть в приложении-аутентификаторе</a>
          <input name="code" inputMode="numeric" required placeholder="Код из приложения" aria-label="Код подтверждения" className="max-w-[12rem] rounded-lg border border-border bg-surface px-3 py-2" />
          <Button type="submit" className="self-start">Подтвердить</Button>
        </form>
      )}
      {state.enabled && (
        <Button variant="ghost" onClick={() => {
          const code = prompt("Код из приложения");
          const password = code && prompt("Пароль от аккаунта");
          if (code && password) disable2fa(code, password).then((r) => setState({ ...state, ...r })).catch(err);
        }}>Отключить</Button>
      )}
    </Card>
  );
}
