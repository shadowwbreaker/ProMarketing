import Link from "next/link";

export const metadata = { title: "Документация — ProMarketing" };

export default function GuidePage() {
  const link = "font-semibold text-accent underline";
  const section = "scroll-mt-24 border-t border-border pt-5";
  const list = "mt-3 list-decimal space-y-2 pl-5 leading-relaxed";
  return (
    <article className="mx-auto max-w-3xl space-y-7">
      <header>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Документация</h1>
        <p className="mt-3 text-muted">Как купить рекламу, выставить канал и провести заказ в ProMarketing.</p>
      </header>
      <nav aria-label="Разделы документации" className="flex flex-wrap gap-2">
        {[["buy", "Покупка рекламы"], ["sell", "Продажа рекламы"], ["stats", "Статистика"], ["help", "Сообщения и помощь"]].map(([id, label]) =>
          <a key={id} href={`#${id}`} className="rounded-lg border border-border px-3 py-2 text-sm font-medium text-accent hover:bg-bg">{label}</a>)}
      </nav>
      <section id="buy" className={section}>
        <h2 className="text-xl font-bold">Купить рекламу</h2>
        <ol className={list}>
          <li>Войдите или <Link href="/register" className={link}>зарегистрируйтесь</Link>. В <Link href="/catalog" className={link}>каталоге</Link> найдите канал или сетку и сравните цену, формат и условия размещения.</li>
          <li>При необходимости напишите продавцу из объявления. Выберите формат, нажмите «Купить» и заполните ТЗ. В тестовом режиме оплата имитируется, деньги не списываются.</li>
          <li>Откройте заказ из <Link href="/purchases" className={link}>«Покупок»</Link> или чата. Передайте материалы. После публикации проверьте ссылку и соответствие условиям, затем подтвердите выполнение или запросите исправление.</li>
          <li>После выполнения оставьте отзыв. Если проблема не решена, нажмите «Пожаловаться» в заказе и приложите подтверждающие материалы.</li>
        </ol>
      </section>
      <section id="sell" className={section}>
        <h2 className="text-xl font-bold">Предложить рекламу на своём канале</h2>
        <ol className={list}>
          <li>Нажмите <Link href="/account/accounts/new" className={link}>«Добавить канал»</Link> и выберите TikTok или YouTube. Для TikTok пройдите вход владельца. Для YouTube выполните подтверждение с кодом в описании канала.</li>
          <li>Настройте рекламные форматы, цену и сроки. Опубликуйте объявление в каталоге. В «Сетках каналов» можно объединить предложения нескольких каналов в один заказ.</li>
          <li>После первого оплаченного заказа появится раздел <Link href="/orders" className={link}>«Заказы»</Link>. Исходное ТЗ покупателя появится в общем чате. Откройте заказ и примите его или укажите причину отказа.</li>
          <li>Согласуйте детали и разместите рекламу. Отправьте ссылку на публикацию через карточку заказа и следите там за подтверждением. В списке заказов доступны фильтры, статистика и выгрузка.</li>
        </ol>
      </section>
      <section id="stats" className={section}>
        <h2 className="text-xl font-bold">Как читать статистику</h2>
        <p className="mt-3 leading-relaxed">В карточке канала указаны источник и дата статистики, если они доступны. Числа с пометкой «Вручную» указал продавец. Для подтверждённого YouTube-канала карточка показывает просмотры последнего доступного ролика и данные по недавним роликам, если они были получены из YouTube. Эти просмотры относятся к опубликованным роликам и не гарантируют охват будущего размещения.</p>
        <p className="mt-2 leading-relaxed">Владелец канала может запросить свежие данные через «Мои каналы» → карточка канала → «Обновить статистику».</p>
      </section>
      <section id="help" className={section}>
        <h2 className="text-xl font-bold">Сообщения и помощь</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 leading-relaxed">
          <li>У каждого собеседника одна переписка в <Link href="/messages" className={link}>«Сообщениях»</Link>. В ней видны сообщения, ТЗ и события заказов. Карточка заказа открывает тот же чат рядом с деталями сделки.</li>
          <li>Красная точка отмечает непрочитанное. Звуковые уведомления включаются в меню профиля через «Звук сообщений».</li>
          <li>По вопросу о конкретном заказе воспользуйтесь чатом или жалобой в его карточке. Для общего вопроса откройте <Link href="/support" className={link}>«Помощь»</Link>. Ответ появится в разделе «Обращения в поддержку» в настройках.</li>
        </ul>
      </section>
      <p className="text-sm text-muted">Обязанности покупателя и владельца канала описаны в <Link href="/rules" className={link}>правилах платформы</Link>.</p>
    </article>
  );
}
