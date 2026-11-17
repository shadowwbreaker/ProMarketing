"""Retire known sample identities while preserving orders, messages and audit records."""
from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.db.models import Q


def retire_seed_accounts(apps, schema_editor):
    db = schema_editor.connection.alias
    User = apps.get_model("accounts", "User")
    known = [
        "demo-buyer@example.com", "demo-seller1@example.com", "demo-seller2@example.com",
        "demo-admin@example.com", "demo-support@example.com", "demo-arbitrator@example.com",
        "demo-owner@example.com", "beta-catalog-seller@example.invalid",
    ]
    users = list(User.objects.using(db).filter(
        Q(email__in=known) | Q(email__iregex=r"^(e2e|seller)[0-9]{10,}@example[.]com$"),
    ).values_list("pk", flat=True))
    if not users:
        return
    accounts = apps.get_model("social_data", "SocialAccount").objects.using(db).filter(owner_id__in=users)
    apps.get_model("catalog", "AdvertisingOffer").objects.using(db).filter(
        social_account_id__in=accounts.values("pk"),
    ).update(is_active=False)
    accounts.update(is_listed=False)
    apps.get_model("catalog", "AccountNetwork").objects.using(db).filter(owner_id__in=users).update(is_active=False)
    apps.get_model("support", "SupportTicket").objects.using(db).filter(author_id__in=users).update(
        status="closed", assignee_id=None,
    )
    apps.get_model("support", "SupportTicket").objects.using(db).filter(assignee_id__in=users).update(assignee_id=None)
    cases = apps.get_model("support", "Dispute").objects.using(db)
    cases.filter(assignee_id__in=users).update(assignee_id=None)
    archived_cases = cases.filter(order__buyer_id__in=users, order__seller_id__in=users)
    apps.get_model("support", "DisputeItem").objects.using(db).filter(
        dispute_id__in=archived_cases.values("pk"),
    ).update(is_active=False)
    archived_cases.update(status="CLOSED")
    apps.get_model("accounts", "UserRole").objects.using(db).filter(user_id__in=users).delete()
    apps.get_model("accounts", "UserProfile").objects.using(db).filter(user_id__in=users).update(
        display_name="Архив тестовых данных", bio="", avatar_key="",
    )
    for pk in users:
        User.objects.using(db).filter(pk=pk).update(
            email=f"archived-seed-{pk}@accounts.invalid", password=make_password(None),
            is_active=False, is_email_verified=False, is_staff=False, is_superuser=False, status="blocked",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_reverify_legacy_signup_emails"),
        ("support", "0004_arbitration_queue"),
        ("catalog", "0001_initial"),
    ]
    operations = [migrations.RunPython(retire_seed_accounts, migrations.RunPython.noop)]
