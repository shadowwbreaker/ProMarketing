import Link from "next/link";

export default function HomePage() {
  return (
    <section className="grid gap-8 py-8 md:grid-cols-[1.4fr_1fr] md:items-center">
      <div>
        <h1 className="text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">
          Реклама у авторов коротких видео — <span className="text-accent">с защитой сделки</span>
        </h1>
        <p className="mt-4 max-w-xl text-muted">
          Находите аккаунты TikTok и YouTube Shorts по реальной статистике, покупайте размещения и получайте
          результат. Деньги переводятся продавцу только после подтверждения выполнения.
        </p>
        <div className="mt-6 flex gap-3">
          <Link href="/catalog" className="rounded-lg bg-accent px-5 py-3 font-semibold text-accent-ink">
            Открыть каталог
          </Link>
          <Link href="/register" className="rounded-lg border border-border bg-surface px-5 py-3 font-semibold">
            Стать продавцом
          </Link>
        </div>
      </div>
      <ul className="grid gap-3 text-sm">
        {[
          ["Статистика по запросу", "Средние просмотры последних 15 видео из официальных API"],
          ["Защита сделки", "Оплата удерживается у платёжного провайдера до выполнения"],
          ["Арбитраж", "Споры рассматривает администрация по фактам и доказательствам"],
        ].map(([t, d]) => (
          <li key={t} className="rounded-xl border border-border bg-surface p-4">
            <p className="font-semibold">{t}</p>
            <p className="mt-1 text-muted">{d}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
