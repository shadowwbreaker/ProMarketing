import django.db.models.deletion
from django.db import migrations, models


def preserve_existing_cases(apps, schema_editor):
    dispute = apps.get_model("support", "Dispute")
    db = schema_editor.connection.alias
    dispute.objects.using(db).all().update(intake_category="order")
    dispute.objects.using(db).filter(status__in=("ESCALATED", "APPEALED"), appeals__isnull=True).update(
        referred_at=models.F("updated_at"), assignee=None,
    )


class Migration(migrations.Migration):
    dependencies = [("support", "0003_dispute_items_status_ticket_messages")]
    operations = [
        migrations.AddField(model_name="dispute", name="intake_category",
                            field=models.CharField(blank=True, default="", max_length=16)),
        migrations.AddField(model_name="dispute", name="referred_at",
                            field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="supportticket", name="arbitration", field=models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
            related_name="intake_tickets", to="support.dispute",
        )),
        migrations.RunPython(preserve_existing_cases, migrations.RunPython.noop),
    ]
