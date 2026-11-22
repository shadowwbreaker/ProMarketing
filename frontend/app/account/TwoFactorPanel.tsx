"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { confirm2fa, disable2fa, get2fa, setup2fa } from "@/lib/api/auth";
import { fieldErrors } from "@/lib/forms";

export function TwoFactorPanel() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [state, setState] = useState<{ enabled: boolean; required: boolean }>();
  const [setup, setSetup] = useState<{ secret: string; otpauth_url: string }>();
  useEffect(() => void get2fa().then(setState).catch(() => {}), []);
  if (!state) return null;
  const err = (e: unknown) => toast(fieldErrors(e).form ?? "Ошибка", "error");

  async function beginSetup() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try { setSetup(await setup2fa()); }
    catch (ex) { err(ex); }
    finally { pending.current = false; setBusy(false); }
  }

  async function confirm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (pending.current) return;
    const code = String(new FormData(e.currentTarget).get("code"));
    pending.current = true;
    setBusy(true);
    try {
      setState({ ...state!, ...(await confirm2fa(code)) });
      setSetup(undefined);
      toast("Двухфакторная защита включена", "success");
    } catch (ex) { err(ex); }
    finally { pending.current = false; setBusy(false); }
  }

  return (
    <Card>
      <h2 className="mb-1 font-bold">Двухфакторная защита</h2>
      <p className="mb-3 text-sm text-muted">
        {state.enabled ? "Включена: при входе нужен код из приложения-аутентификатора." : state.required ? "Обязательна для служебного раздела." : "Дополнительная защита входа кодом из приложения (Google Authenticator, Яндекс Ключ и др.)."}
      </p>
      {!state.enabled && !setup && <Button variant="secondary" loading={busy} onClick={() => void beginSetup()}>Включить</Button>}
      {setup && (
        <form onSubmit={confirm} className="flex flex-col gap-2 text-sm">
          <p id="two-factor-qr-help">Откройте Google Authenticator или другое приложение-аутентификатор, нажмите «+» и отсканируйте QR-код.</p>
          <QRCodeSVG
            value={setup.otpauth_url}
            size={224}
            marginSize={4}
            level="M"
            role="img"
            aria-label="QR-код для подключения двухфакторной защиты"
            aria-describedby="two-factor-qr-help"
            className="h-auto max-w-full self-start rounded-lg border border-border"
          />
          <p>Не получается отсканировать? Добавьте в приложение ключ вручную: <code className="break-all font-mono">{setup.secret}</code></p>
          <a className="text-accent" href={setup.otpauth_url}>Открыть в приложении-аутентификаторе</a>
          <label className="mt-2 flex flex-col gap-1 self-start">Шестизначный код из приложения
            <input name="code" type="text" inputMode="numeric" autoComplete="one-time-code" spellCheck={false} required
              minLength={6} maxLength={6} pattern="[0-9]{6}" aria-describedby="two-factor-confirm-help"
              className="w-48 max-w-full rounded-lg border border-border bg-surface px-3 py-2" />
          </label>
          <p id="two-factor-confirm-help" className="text-muted">Защита включится только после подтверждения кода.</p>
          <Button type="submit" className="self-start" loading={busy}>Подтвердить</Button>
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
