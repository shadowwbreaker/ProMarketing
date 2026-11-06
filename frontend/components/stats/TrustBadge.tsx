import type { TrustStatus } from "@/lib/api/social";

const MAP: Record<TrustStatus, { label: string; cls: string; hint: string }> = {
  VERIFIED: { label: "Подтверждено", cls: "bg-ok/15 text-ok", hint: "Получено из официального API платформы" },
  MANUAL: { label: "Вручную", cls: "bg-warn/15 text-warn", hint: "Введено владельцем, не проверено платформой" },
  STALE: { label: "Устарело", cls: "bg-muted/15 text-muted", hint: "Статистика давно не обновлялась" },
  UNAVAILABLE: { label: "Недоступно", cls: "bg-muted/15 text-muted", hint: "Данные получить нельзя" },
  SUSPICIOUS: { label: "На проверке", cls: "bg-danger/15 text-danger", hint: "Обнаружены подозрительные изменения" },
  ERROR: { label: "Ошибка", cls: "bg-danger/15 text-danger", hint: "Последнее получение данных не удалось" },
};

export function TrustBadge({ status }: { status: TrustStatus }) {
  const m = MAP[status];
  return (
    <span title={m.hint} className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${m.cls}`}>
      {m.label}
    </span>
  );
}
