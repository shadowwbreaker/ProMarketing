import type { OrderTerms } from "@/lib/api/orders";
import { formatDateTime } from "@/lib/format";

const removalLabels: Record<string, string> = {
  refund_or_repeat: "Возврат или повторная публикация",
  seller_not_liable: "Продавец не несёт ответственность",
  full_refund: "Полный возврат",
};

export function OrderTermsDetails({ terms }: { terms: OrderTerms }) {
  const date = (value: unknown) => typeof value === "string" ? formatDateTime(value) : "";
  const fields = [
    ["Бренд или продукт", terms.brand], ["Сайт", terms.site_url], ["Техническое задание", terms.brief],
    ["Текст рекламы", terms.ad_text], ["Призыв к действию", terms.cta],
    ["Ссылки", Array.isArray(terms.links) ? terms.links.join("\n") : ""],
    ["Публикация до", date(terms.publish_deadline)], ["Передача материалов до", date(terms.materials_deadline)],
    ["Срок размещения", terms.placement_days ? `${terms.placement_days} дн.` : ""],
    ["Дополнительные требования", terms.extra_requirements],
    ["Если платформа удалит видео", removalLabels[String(terms.platform_removal_policy)]],
    ["Отчёт по просмотрам", terms.results_report ? "Запрошен" : ""],
  ];
  return (
    <dl className="grid gap-3 text-sm">
      {fields.filter(([, value]) => Boolean(value)).map(([label, value]) => (
        <div key={String(label)}>
          <dt className="text-xs font-medium text-muted">{String(label)}</dt>
          <dd className="mt-0.5 whitespace-pre-wrap break-words">{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
