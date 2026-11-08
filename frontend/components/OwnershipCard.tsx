"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { checkOwnership, SocialAccount, startOwnership } from "@/lib/api/social";
import { fieldErrors } from "@/lib/forms";

/** D-020: owner proves the channel is theirs by putting a short code into the channel description. */
export function OwnershipCard({ acc, onVerified }: { acc: SocialAccount; onVerified: (a: SocialAccount) => void }) {
  const [code, setCode] = useState(acc.ownership_code ?? "");
  const [msg, setMsg] = useState<{ text: string; bad?: boolean }>();
  const [busy, setBusy] = useState(false);
  if (acc.ownership_verified || !acc.ownership_check_supported) return null;

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setMsg(undefined);
    try {
      await fn();
    } catch (e) {
      setMsg({ text: fieldErrors(e).form ?? "Ошибка", bad: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="border-warn/60">
      <h2 className="text-lg font-bold">Подтвердите, что канал ваш</h2>
      <p className="mt-1 text-sm text-muted">
        Покупатели больше доверяют каналам с отметкой «владение подтверждено». Это займёт минуту.
      </p>
      {!code ? (
        <Button className="mt-3" loading={busy} onClick={() => run(async () => setCode((await startOwnership(acc.id)).code))}>
          Получить код
        </Button>
      ) : (
        <>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
            <li>
              Скопируйте код: <code className="rounded bg-bg px-2 py-0.5 font-mono font-bold">{code}</code>{" "}
              <button className="text-xs text-accent underline" onClick={() => void navigator.clipboard?.writeText(code)}>копировать</button>
            </li>
            <li>Откройте YouTube Studio → «Настройка» → «Основные сведения» и вставьте код в описание канала.</li>
            <li>Нажмите «Опубликовать» в YouTube Studio, затем «Проверить» здесь.</li>
            <li>После подтверждения код из описания можно удалить.</li>
          </ol>
          <Button className="mt-3" loading={busy} onClick={() => run(async () => {
            const r = await checkOwnership(acc.id);
            if (r.verified) onVerified(r.account);
            else setMsg({ text: "Код в описании канала не найден. Изменения на YouTube иногда появляются через пару минут — попробуйте ещё раз.", bad: true });
          })}>
            Проверить
          </Button>
        </>
      )}
      {msg && <p className={`mt-2 text-sm ${msg.bad ? "text-danger" : "text-ok"}`}>{msg.text}</p>}
    </Card>
  );
}
