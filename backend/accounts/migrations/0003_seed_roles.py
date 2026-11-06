from django.db import migrations

ROLES = {
    "buyer": ("Покупатель", False),
    "seller": ("Продавец", False),
    "support_agent": ("Сотрудник поддержки", True),
    "moderator": ("Модератор", True),
    "admin": ("Администратор", True),
    "super_admin": ("Супер-администратор", True),
}


def seed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, (title, is_staff) in ROLES.items():
        Role.objects.update_or_create(code=code, defaults={"title": title, "is_staff_role": is_staff})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
