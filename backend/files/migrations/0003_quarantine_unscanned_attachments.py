from django.db import migrations


def quarantine_unscanned_attachments(apps, schema_editor):
    attachment = apps.get_model("files", "Attachment")
    attachment.objects.using(schema_editor.connection.alias).filter(scan_status="clean").update(scan_status="pending")


class Migration(migrations.Migration):
    dependencies = [("files", "0002_stored_file")]
    operations = [migrations.RunPython(quarantine_unscanned_attachments, migrations.RunPython.noop)]
