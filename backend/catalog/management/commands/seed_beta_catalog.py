from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserProfile
from accounts.roles import assign_role
from catalog.models import AccountNetwork, AdFormat, AdvertisingOffer, NetworkItem
from catalog.services import set_listing
from social_data.models import DataSource, SocialAccount, SocialAccountStatistics, TrustStatus

SELLER_EMAIL = "beta-catalog-seller@example.invalid"
DESCRIPTION = (
    "Пример для тестовой покупки. Ссылка ведёт на публичный канал. "
    "Владелец канала не участвует в сделке. Статистика и цена условные."
)
CONDITIONS = "Тестовое размещение. Реклама не публикуется, деньги не списываются."
CHANNELS = (
    ("youtube", "crashcourse", "Crash Course", "Образование", 125000, 56000, 180000),
    ("youtube", "scishow", "SciShow", "Наука", 84000, 30000, 140000),
    ("youtube", "NASAJPL", "NASA JPL", "Космос", 62000, 22000, 115000),
    ("tiktok", "natgeo", "National Geographic", "Природа", 94000, 41000, 155000),
    ("tiktok", "duolingo", "Duolingo", "Образование", 111000, 51000, 170000),
)
NETWORKS = (
    ("Наука и космос", ("scishow", "NASAJPL")),
    ("Образование и природа", ("crashcourse", "natgeo", "duolingo")),
)


class Command(BaseCommand):
    help = "Populate the beta catalog with labelled sample offers and networks"

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.BETA_MODE or settings.PAYMENT_PROVIDER != "mock":
            raise CommandError("The demo catalog requires BETA_MODE and mock payments")

        seller, created = User.objects.get_or_create(email=SELLER_EMAIL, defaults={"is_email_verified": True})
        if created:
            seller.set_unusable_password()
            seller.save(update_fields=["password"])
            UserProfile.objects.create(user=seller, display_name="Демо-продавец ProMarketing", bio=DESCRIPTION)
        elif seller.has_usable_password() or seller.is_staff or seller.is_superuser:
            raise CommandError("The demo seller email is already in use")
        assign_role(seller, "seller")

        offers = {}
        for platform, handle, name, category, followers, views, price in CHANNELS:
            url = (f"https://www.youtube.com/@{handle}/shorts" if platform == "youtube"
                   else f"https://www.tiktok.com/@{handle}")
            account, _ = SocialAccount.objects.get_or_create(
                platform=platform, external_id=f"beta-catalog:{handle.lower()}",
                defaults={"owner": seller, "handle": handle, "profile_url": url, "title": f"Демо · {name}",
                          "category": category, "language": "en", "description": DESCRIPTION},
            )
            if account.owner_id != seller.pk:
                raise CommandError(f"Demo channel {handle} is already in use")
            if account.current_statistics_id is None:
                account.current_statistics = SocialAccountStatistics.objects.create(
                    social_account=account, followers=followers, avg_views=views, videos_in_sample=15,
                    source=DataSource.MANUAL, trust_status=TrustStatus.MANUAL, fetched_at=timezone.now(),
                    notes="Условная статистика для демонстрации",
                )
                account.save(update_fields=["current_statistics"])

            offer, _ = AdvertisingOffer.objects.get_or_create(
                social_account=account, ad_format=AdFormat.INTEGRATION, is_active=True,
                defaults={"title": "Демонстрационное размещение", "conditions": CONDITIONS,
                          "price_minor": price, "placement_days": 7, "publish_within_days": 3},
            )
            if not account.is_listed:
                set_listing(account, user=seller, listed=True)
            offers[handle] = offer

        for name, handles in NETWORKS:
            network, _ = AccountNetwork.objects.get_or_create(
                owner=seller, title=f"Демо-сетка · {name}",
                defaults={"description": DESCRIPTION, "conditions": CONDITIONS},
            )
            for handle in handles:
                offer = offers[handle]
                NetworkItem.objects.get_or_create(
                    network=network, social_account=offer.social_account,
                    defaults={"offer": offer, "price_minor": offer.price_minor},
                )
        self.stdout.write(self.style.SUCCESS(f"Published {len(offers)} demo offers and {len(NETWORKS)} demo networks"))
