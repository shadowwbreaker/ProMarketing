"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { FormError } from "@/components/AuthCard";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { becomeSeller } from "@/lib/api/auth";
import { createOffer, getAdFormats, rublesToMinor, setListing } from "@/lib/api/catalog";
import { ApiError } from "@/lib/api/client";
import { checkClaim, createSocialAccount, getSocialAccount, saveManualStats, SocialAccount, startClaim, startTikTokOAuth } from "@/lib/api/social";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { Platform, validateProfileUrl } from "@/lib/profile-url";
import { formatCount } from "@/lib/format";

type Step = 1 | 2 | 3 | 4;

const PLATFORMS: { value: Platform; label: string; disabled?: boolean; note?: string }[] = [
  { value: "tiktok", label: "TikTok" },
  { value: "youtube", label: "YouTube Shorts" },
  { value: "instagram", label: "Instagram Reels — недоступно", disabled: true },
];

const PLACEHOLDER: Record<Platform, string> = {
  tiktok: "https://www.tiktok.com/@ваш_ник",
  youtube: "https://www.youtube.com/@канал/shorts",
  instagram: "",
};

function Steps({ step }: { step: Step }) {
  const names = ["Платформа", "Ссылка", "Статистика", "Объявление"];
  return (
    <ol className="mb-6 grid grid-cols-4 gap-2 text-center text-xs">
      {names.map((n, i) => (
        <li key={n} className={`rounded-lg border px-1 py-2 ${i + 1 === step ? "border-accent font-bold" : i + 1 < step ? "border-border text-muted" : "border-border text-muted opacity-60"}`}>
          <span className="block text-base">{i + 1 < step ? "✓" : i + 1}</span>{n}
        </li>
      ))}
    </ol>
  );
}

export default function NewAccountPage() {
  return <Suspense><NewAccountWizard /></Suspense>;
}

function NewAccountWizard() {
  const params = useSearchParams();
  const router = useRouter();
  const { me, loading: authLoading, refresh } = useAuth();
  useEffect(() => {
    if (!authLoading && !me) router.replace("/register"); // selling starts with an account on ProMarketing
  }, [authLoading, me, router]);
  const [step, setStep] = useState<Step>(1);
  const [platform, setPlatform] = useState<Platform>("tiktok");
  const [url, setUrl] = useState("");
  const [account, setAccount] = useState<SocialAccount>();
  const [manual, setManual] = useState(false);
  const [oauthOffer, setOauthOffer] = useState(false);
  const [claim, setClaim] = useState<{ id: string; code?: string; failed?: boolean }>();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ form?: string; fields: Record<string, string> }>({ fields: {} });
  const [formats, setFormats] = useState<{ value: string; label: string }[]>([]);

  useEffect(() => {
    getAdFormats().then(setFormats).catch(() => {});
  }, []);

  // Resume after "Войти через TikTok": the OAuth callback returns here with the created account.
  const resumeId = params.get("account");
  useEffect(() => {
    if (!resumeId) return;
    getSocialAccount(resumeId).then((a) => { setAccount(a); setPlatform(a.platform); setStep(3); }).catch((e) => setErr(fieldErrors(e)));
  }, [resumeId]);

  // Poll while the one-off statistics job runs (no monitoring: a single job per request).
  const pending = account?.refresh?.last_job && ["queued", "running"].includes(account.refresh.last_job.status);
  useEffect(() => {
    if (!account || !pending) return;
    const t = setTimeout(() => getSocialAccount(account.id).then(setAccount).catch(() => {}), 1500);
    return () => clearTimeout(t);
  }, [account, pending]);

  async function ensureSeller() {
    if (me && !me.permissions.includes("account.manage_own")) {
      await becomeSeller();
      await refresh();
    }
  }

  async function submitLink(e: FormEvent) {
    e.preventDefault();
    const problem = validateProfileUrl(platform, url);
    if (problem) return setErr({ fields: { profile_url: problem } });
    setBusy(true);
    setErr({ fields: {} });
    try {
      await ensureSeller();
      const acc = await createSocialAccount({ profile_url: url.trim(), manual });
      setAccount(acc);
      setStep(3);
    } catch (ex) {
      if (ex instanceof ApiError && (ex.code === "oauth_required" || ex.details?.manual_allowed)) setOauthOffer(true);
      if (ex instanceof ApiError && ex.code === "account_claimable") setClaim({ id: String(ex.details?.account_id) });
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  async function connectTikTok() {
    try {
      await ensureSeller();
      const { authorize_url } = await startTikTokOAuth();
      window.location.href = authorize_url;
    } catch (ex) {
      setErr(fieldErrors(ex));
    }
  }

  async function submitManualStats(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!account) return;
    const f = new FormData(e.currentTarget);
    const followers = Number(f.get("followers"));
    const avg = Number(f.get("avg_views"));
    if (!Number.isFinite(followers) || followers < 0 || !Number.isFinite(avg) || avg < 0)
      return setErr({ fields: { followers: "Укажите неотрицательные числа" } });
    setBusy(true);
    try {
      setAccount(await saveManualStats(account.id, Math.round(followers), [Math.round(avg)]));
      setErr({ fields: {} });
    } catch (ex) {
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  async function submitOffer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!account) return;
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setErr({ fields: {} });
    try {
      await createOffer(account.id, {
        title: String(f.get("title") ?? ""),
        conditions: String(f.get("conditions") ?? ""),
        publish_within_days: Number(f.get("publish_within_days")),
        placement_days: Number(f.get("placement_days")),
        price_minor: rublesToMinor(String(f.get("price") ?? "")),
        ad_format: String(f.get("ad_format")),
      });
      try {
        await setListing(account.id, true);
        router.push(`/account/accounts/${account.id}?created=1`);
      } catch (ex) {
        // Offer saved, but publication needs something else (e.g. confirmed email) — show the reason on the account page.
        router.push(`/account/accounts/${account.id}?listing_error=${encodeURIComponent(fieldErrors(ex).form ?? "")}`);
      }
    } catch (ex) {
      setErr(fieldErrors(ex));
    } finally {
      setBusy(false);
    }
  }

  const stats = account?.statistics;
  const hasStats = stats && stats.followers != null;
  const failed = account?.refresh?.last_job?.status === "failed";

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-4 text-2xl font-bold">Добавить канал</h1>
      <Steps step={step} />
      <FormError message={err.form} />

      {step === 1 && (
        <Card className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm font-medium">
            Платформа
            <select
              name="platform"
              value={platform}
              onChange={(e) => setPlatform(e.target.value as Platform)}
              className="rounded-lg border border-border bg-surface px-3 py-2 font-normal"
            >
              {PLATFORMS.map((p) => (
                <option key={p.value} value={p.value} disabled={p.disabled}>{p.label}</option>
              ))}
            </select>
          </label>
          <p className="text-xs text-muted">
            Instagram недоступен: с 1 сентября 2025 года в России запрещено размещать рекламу в сервисах Meta.
          </p>
          <Button onClick={() => setStep(2)}>Далее</Button>
        </Card>
      )}

      {step === 2 && (
        <Card>
          <form onSubmit={submitLink} className="flex flex-col gap-4" noValidate>
            <Field
              label={platform === "youtube" ? "Ссылка на страницу Shorts канала" : "Ссылка на профиль TikTok"}
              name="profile_url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={PLACEHOLDER[platform]}
              error={err.fields.profile_url}
              hint={platform === "youtube" ? "Обязательно со /shorts в конце" : undefined}
              required
            />
            {platform === "tiktok" && (
              <p className="text-xs text-muted">
                Чтобы подписчики и просмотры посчитались автоматически, TikTok требует входа владельца канала —
                так же подтверждается, что канал ваш.
              </p>
            )}
            {(oauthOffer || manual) && platform === "tiktok" && (
              <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
                <Button type="button" onClick={connectTikTok}>Войти через TikTok</Button>
                <p className="text-center text-xs text-muted">или</p>
              </div>
            )}
            {claim && (
              <div className="flex flex-col gap-2 rounded-lg border border-warn/60 p-3 text-sm">
                {!claim.code ? (
                  <Button type="button" variant="secondary" onClick={() => startClaim(claim.id).then((r) => setClaim({ ...claim, code: r.code })).catch((e) => setErr(fieldErrors(e)))}>
                    Это мой канал — получить код
                  </Button>
                ) : (
                  <>
                    <p>
                      Вставьте код <code className="rounded bg-bg px-1.5 font-mono font-bold">{claim.code}</code> в описание канала
                      (YouTube Studio → «Настройка» → «Основные сведения»), опубликуйте и нажмите «Проверить».
                    </p>
                    {claim.failed && <p className="text-danger">Код в описании не найден. Изменения на YouTube иногда появляются через пару минут.</p>}
                    <Button type="button" onClick={() => checkClaim(claim.id).then((r) => {
                      if (r.claimed && r.account) { setAccount(r.account); setErr({ fields: {} }); setStep(3); }
                      else setClaim({ ...claim, failed: true });
                    }).catch((e) => setErr(fieldErrors(e)))}>Проверить</Button>
                  </>
                )}
              </div>
            )}
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" name="manual" checked={manual} onChange={(e) => setManual(e.target.checked)} className="mt-1" />
              <span>Указать статистику вручную — на карточке будет пометка «Вручную»</span>
            </label>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={() => setStep(1)}>Назад</Button>
              <Button type="submit" loading={busy} className="flex-1">Далее</Button>
            </div>
          </form>
        </Card>
      )}

      {step === 3 && account && (
        <Card className="flex flex-col gap-4">
          <p className="text-sm text-muted">{account.title || account.handle}</p>
          {pending && <p className="text-sm">Считаем подписчиков и просмотры последних 15 видео…</p>}
          {failed && (
            <p className="text-sm text-danger">
              Не удалось получить статистику: {account.refresh?.last_job?.error_message || "ошибка платформы"}. Введите её вручную.
            </p>
          )}
          {hasStats && (
            <div className="grid grid-cols-2 gap-3 text-center">
              <div className="rounded-lg border border-border p-3">
                <p className="text-2xl font-bold">{formatCount(stats.followers ?? 0)}</p>
                <p className="text-xs text-muted">подписчиков</p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-2xl font-bold">{stats.avg_views != null ? formatCount(stats.avg_views) : "—"}</p>
                <p className="text-xs text-muted">
                  среднее просмотров{stats.videos_in_sample > 1 ? ` (${stats.videos_in_sample} видео)` : ""}
                </p>
              </div>
              {stats.trust_status === "MANUAL" && <p className="col-span-2 text-xs text-muted">Пометка «Вручную»</p>}
              {stats.derived_metrics_note && <p className="col-span-2 text-xs text-muted">{stats.derived_metrics_note}</p>}
            </div>
          )}
          {!hasStats && !pending && (
            <form onSubmit={submitManualStats} className="grid grid-cols-2 gap-3" noValidate>
              <Field label="Подписчиков" name="followers" type="number" min={0} required error={err.fields.followers} />
              <Field label="Среднее просмотров (15 видео)" name="avg_views" type="number" min={0} required />
              <Button type="submit" loading={busy} className="col-span-2">Сохранить</Button>
            </form>
          )}
          <Button disabled={!hasStats} onClick={() => setStep(4)}>Далее</Button>
        </Card>
      )}

      {step === 4 && account && (
        <Card>
          <form onSubmit={submitOffer} className="flex flex-col gap-4" noValidate>
            <div className="flex flex-col gap-1 text-sm">
              <span className="font-medium">Ссылка на канал</span>
              <a href={account.profile_url} target="_blank" rel="noopener noreferrer nofollow"
                className="truncate rounded-lg border border-border bg-bg px-3 py-2 text-accent hover:underline">{account.profile_url}</a>
              <span className="text-xs text-muted">Покупатели увидят её в объявлении и смогут сразу открыть канал.</span>
            </div>
            <Field label="Название объявления" name="title" required maxLength={120} placeholder="Реклама в моих Shorts" error={err.fields.title} />
            <label className="flex flex-col gap-1 text-sm font-medium">
              Формат рекламы
              <select name="ad_format" defaultValue="integration" className="rounded-lg border border-border bg-surface px-3 py-2 font-normal">
                {formats.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium">
              Условия работы
              <textarea name="conditions" rows={4} required className="rounded-lg border border-border bg-surface px-3 py-2 font-normal"
                placeholder="Что входит, что нужно от рекламодателя, правки" />
              {err.fields.conditions && <span className="text-xs text-danger">{err.fields.conditions}</span>}
            </label>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Срок выполнения, дней" name="publish_within_days" type="number" min={1} max={90} defaultValue={3} required error={err.fields.publish_within_days} />
              <Field label="Ролик висит, дней" name="placement_days" type="number" min={1} max={365} defaultValue={30} required error={err.fields.placement_days} />
            </div>
            <Field label="Цена, ₽" name="price" inputMode="decimal" required error={err.fields.price_minor} />
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={() => setStep(3)}>Назад</Button>
              <Button type="submit" loading={busy} className="flex-1">Создать</Button>
            </div>
          </form>
        </Card>
      )}

      <p className="mt-6 text-center text-xs text-muted">
        Статистика собирается один раз сейчас и потом только по кнопке «Обновить». <Link href="/account?tab=accounts" className="underline">Мои каналы</Link>
      </p>
    </div>
  );
}
