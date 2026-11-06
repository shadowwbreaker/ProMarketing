from django.db import migrations

from common.db import append_only_trigger_sql

TABLES = ["orders_orderevent", "orders_ordertermsversion"]


class Migration(migrations.Migration):
    dependencies = [("orders", "0001_initial")]
    operations = [migrations.RunSQL(*append_only_trigger_sql(t)) for t in TABLES]
