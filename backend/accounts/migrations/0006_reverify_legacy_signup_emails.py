from django.db import migrations
from django.db.models import Exists, OuterRef


def reverify_legacy_signup_emails(apps, schema_editor):
    user = apps.get_model("accounts", "User")
    log = apps.get_model("audit", "AuditLog")
    events = log.objects.using(schema_editor.connection.alias).filter(
        actor_id=OuterRef("pk"), subject_type="user",
    )
    user.objects.using(schema_editor.connection.alias).filter(
        is_email_verified=True,
    ).filter(
        Exists(events.filter(action="user.registered")),
        ~Exists(events.filter(action__in=["user.email_verified", "user.password_reset"])),
    ).update(is_email_verified=False)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_avatar"), ("audit", "0002_append_only_triggers")]
    operations = [migrations.RunPython(reverify_legacy_signup_emails, migrations.RunPython.noop)]
