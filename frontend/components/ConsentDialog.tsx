"use client";

import { useEffect, useId, useRef, useState } from "react";

/** Must match backend social_data/consent.py CONSENT_TEXT (version 2026-11-09). */
export const CONSENT_TEXT =
  "Я владелец этого канала и разрешаю ProMarketing один раз получить из официального API платформы " +
  "число подписчиков и просмотры последних 15 видео, чтобы показать их покупателям в объявлении. " +
  "Повторно данные запрашиваются только когда я нажимаю «Обновить статистику».";

const PLATFORM_NOTE: Record<string, string> = {
  tiktok: "TikTok попросит войти в аккаунт и подтвердить доступ — так платформа убеждается, что канал ваш.",
  youtube: "Данные запрашиваются через официальный YouTube Data API. Пароль от канала не нужен.",
};

/**
 * Owner consent before any request to the platform API (D-024): on adding a channel and on every refresh.
 * Fades/scales in; Esc and the backdrop close it; the continue button stays disabled until the box is ticked.
 */
export function ConsentDialog({ open, platform, title, onConfirm, onCancel }: {
  open: boolean;
  platform: string;
  title: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [checked, setChecked] = useState(false);
  const box = useRef<HTMLInputElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    setChecked(false);
    box.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-[opacity,visibility] duration-200 ${open ? "visible opacity-100" : "invisible opacity-0"}`}
      inert={!open}>
      <div aria-hidden onClick={onCancel} className="absolute inset-0 bg-black/40" />
      <div role="dialog" aria-modal="true" aria-labelledby={`${id}-t`}
        className={`relative w-full max-w-md rounded-2xl bg-surface p-6 shadow-2xl transition-[scale,translate] duration-200 ease-[cubic-bezier(0.2,0,0,1)] motion-reduce:transition-none
          ${open ? "translate-y-0 scale-100" : "translate-y-2 scale-[0.96]"}`}>
        <h2 id={`${id}-t`} className="text-lg font-bold">{title}</h2>
        <p className="mt-2 text-sm text-muted">{PLATFORM_NOTE[platform] ?? ""}</p>
        <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-border p-4 text-sm leading-relaxed transition-colors duration-150 has-[:checked]:border-accent has-[:checked]:bg-accent/[0.04]">
          <input ref={box} type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)}
            className="mt-1 h-4 w-4 shrink-0 accent-[var(--accent)]" aria-label="Разрешаю получить статистику канала" />
          <span>{CONSENT_TEXT}</span>
        </label>
        <div className="mt-5 flex gap-2">
          <button type="button" onClick={onCancel} className="rounded-lg border border-border px-4 py-2 text-sm font-semibold">Отмена</button>
          <button type="button" disabled={!checked} onClick={onConfirm}
            className="flex-1 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink transition-[opacity,scale] duration-150 enabled:active:scale-[0.96] disabled:opacity-40">
            {platform === "tiktok" ? "Разрешаю — войти через TikTok" : "Разрешаю и продолжаю"}
          </button>
        </div>
      </div>
    </div>
  );
}
