from django.db import migrations

from common.db import append_only_trigger_sql

TABLES = ["payments_financialledgerentry"]


class Migration(migrations.Migration):
    dependencies = [("payments", "0002_initial")]
    operations = [migrations.RunSQL(*append_only_trigger_sql(t)) for t in TABLES]
