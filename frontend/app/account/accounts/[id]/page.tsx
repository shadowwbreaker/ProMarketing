"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { TrustBadge } from "@/components/stats/TrustBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import {
  getSocialAccount,
  getStatsHistory,
  PLATFORM_LABEL,
  refreshSocialAccount,
  saveManualStats,
  SocialAccount,
  StatsHistory,
} from "@/lib/api/social";
import { fieldErrors } from "@/lib/forms";
import { formatCount, formatDateTime } from "@/lib/format";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [acc, setAcc] = useState<SocialAccount>();
  const [hist, setHist] = useState<StatsHistory>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, h] = await Promise.all([getSocialAccount(id), getStatsHistory(id)]);
      setAcc(a);
      setHist(h);
      setError(undefined);
      return a;
    } catch (e) {
      setError(fieldErrors(e).form);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  // While a job is queued/running, poll a few times (this polls OUR backend, not the social platform).
  useEffect(() => {
    const st = acc?.refresh?.last_job?.status;
    if (st !== "queued" && st !== "running") return;
    const t = setTimeout(() => void load(), 2000);
    return () => clearTimeout(t);
  }, [acc, load]);

  async function refresh() {
    setBusy(true);
    try {
      const r = await refreshSocialAccount(id);
      setAcc(r.account);
      toast("Запрос на обновление отправлен", "success");
      await load();
    } catch (e) {
      const msg = fieldErrors(e).form ?? "Ошибка";
      const next = e instanceof ApiError ? (e.details?.next_allowed_at as string | undefined) : undefined;
      toast(next ? `${msg} Следующее обновление: ${formatDateTime(next)}` : msg, "error");
    } finally {
      setBusy(false);
    }
  }

  async function manual(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const views = String(f.get("views") ?? "")
      .split(/[\s,;]+/)
      .filter(Boolean)
      .map(Number);
    try {
      setAcc(await saveManualStats(id, Number(f.get("followers")), views));
      await load();
      toast("Статистика сохранена как ручная", "success");
    } catch (ex) {
      toast(fieldErrors(ex).form ?? "Проверьте значения", "error");
    }
  }

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!acc) return <LoadingState />;
  const s = acc.statistics;
  const job = acc.refresh?.last_job;
  const running = job?.status === "queued" || job?.status === "running";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm text-muted">{PLATFORM_LABEL[acc.platform]}</p>
          <h1 className="text-2xl font-bold">{acc.title}</h1>
          <a href={acc.profile_url} target="_blank" rel="noopener noreferrer nofollow" className="text-sm text-accent">
            @{acc.handle}
          </a>
          {acc.ownership_verified && <span className="ml-2 text-xs text-ok">владение подтверждено</span>}
        </div>
        <div className="text-right">
          <Button onClick={refresh} loading={busy || running} disabled={!!acc.refresh?.next_allowed_at}>
            Обновить статистику
          </Button>
          <p className="mt-1 text-xs text-muted">
            {acc.refresh?.next_allowed_at
              ? `Доступно с ${formatDateTime(acc.refresh.next_allowed_at)}`
              : `Не чаще раза в ${acc.refresh?.interval_hours ?? 24} ч`}
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-xs text-muted">Подписчики</p>
          <p className="text-2xl font-bold">{s.followers != null ? formatCount(s.followers) : "—"}</p>
        </Card>
        <Card>
          <p className="text-xs text-muted">Средние просмотры</p>
          <p className="text-2xl font-bold">{s.avg_views != null ? formatCount(s.avg_views) : "—"}</p>
          <p className="text-xs text-muted">по {s.videos_in_sample} видео</p>
        </Card>
        <Card>
          <p className="text-xs text-muted">Статус данных</p>
          <TrustBadge status={s.trust_status} />
          <p className="mt-1 text-xs text-muted">{s.fetched_at ? `обновлено ${formatDateTime(s.fetched_at)}` : "ещё не получено"}</p>
        </Card>
      </div>
      {s.derived_metrics_note && <p className="text-sm text-warn">{s.derived_metrics_note}</p>}
      {job?.status === "failed" && (
        <p role="alert" className="rounded-lg bg-danger/10 p-3 text-sm text-danger">
          Последнее обновление не удалось: {job.error_message}. Предыдущая статистика сохранена.
        </p>
      )}

      {hist && hist.results[0] && (
        <Card>
          <h2 className="mb-3 font-bold">Видео в выборке</h2>
          <ol className="grid gap-1 text-sm">
            {hist.results[0].videos.map((v) => (
              <li key={v.external_video_id} className="flex justify-between gap-2">
                <a href={v.url} target="_blank" rel="noopener noreferrer nofollow" className="truncate hover:text-accent">
                  {v.published_at ? formatDateTime(v.published_at) : v.external_video_id}
                </a>
                <span className="font-mono">{formatCount(v.views)}</span>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {hist && (
        <Card>
          <h2 className="mb-3 font-bold">История статистики</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-muted">
              <tr><th>Дата</th><th>Подписчики</th><th>Среднее</th><th>Видео</th><th>Статус</th></tr>
            </thead>
            <tbody>
              {hist.results.map((h) => (
                <tr key={h.id} className="border-t border-border">
                  <td>{formatDateTime(h.fetched_at)}</td>
                  <td>{formatCount(h.followers)}</td>
                  <td>{h.avg_views != null ? formatCount(h.avg_views) : "—"}</td>
                  <td>{h.videos_in_sample}</td>
                  <td><TrustBadge status={h.trust_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Card>
        <h2 className="mb-1 font-bold">Ввести статистику вручную</h2>
        <p className="mb-3 text-xs text-muted">Будет отмечена как «Вручную». Покупатели видят этот статус.</p>
        <form onSubmit={manual} className="grid gap-3 sm:grid-cols-[160px_1fr_auto] sm:items-end">
          <label className="flex flex-col text-sm">Подписчики<input name="followers" type="number" min={0} required className="rounded-lg border border-border bg-surface px-3 py-2" /></label>
          <label className="flex flex-col text-sm">Просмотры последних видео (через запятую)<input name="views" required className="rounded-lg border border-border bg-surface px-3 py-2" /></label>
          <Button type="submit" variant="secondary">Сохранить</Button>
        </form>
      </Card>
    </div>
  );
}
