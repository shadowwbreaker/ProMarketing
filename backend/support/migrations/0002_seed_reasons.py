from django.db import migrations

# roadmap 9.2 (buyer) + seller-side reasons (docs/SUPPORT_AND_DISPUTES.md §6)
REASONS = [
    ("seller_not_responding", "Продавец не отвечает", "buyer"),
    ("not_published", "Продавец не опубликовал видео", "buyer"),
    ("deadline_missed", "Продавец нарушил срок публикации", "buyer"),
    ("wrong_material", "Опубликован неправильный рекламный материал", "buyer"),
    ("brief_mismatch", "Реклама не соответствует техническому заданию", "buyer"),
    ("wrong_account", "Использован неправильный аккаунт", "buyer"),
    ("removed_early", "Видео удалено раньше согласованного срока", "buyer"),
    ("partial_fulfilment", "Продавец выполнил только часть заказа", "buyer"),
    ("wrong_link", "Продавец предоставил неправильную ссылку", "buyer"),
    ("fake_statistics", "Статистика аккаунта оказалась недостоверной", "buyer"),
    ("extra_payment", "Продавец требует дополнительную оплату", "buyer"),
    ("off_platform", "Попытка перевести сделку за пределы платформы", "both"),
    ("other", "Другая проблема", "both"),
    ("buyer_not_confirming", "Покупатель не подтверждает выполненный заказ", "seller"),
    ("materials_delayed", "Покупатель не передал рекламные материалы", "seller"),
    ("beyond_brief", "Покупатель требует сверх согласованного ТЗ", "seller"),
]


def seed(apps, schema_editor):
    DisputeReason = apps.get_model("support", "DisputeReason")
    for i, (code, title, allowed) in enumerate(REASONS):
        DisputeReason.objects.update_or_create(code=code, defaults={"title": title, "allowed_for": allowed, "sort": i})


class Migration(migrations.Migration):
    dependencies = [("support", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
