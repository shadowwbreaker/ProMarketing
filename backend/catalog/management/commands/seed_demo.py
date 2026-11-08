"""Demo data for local development. Refuses to run in production."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User, UserProfile
from accounts.roles import assign_role
from catalog.models import AccountNetwork, AdvertisingOffer, NetworkItem
from social_data.models import SocialAccount, SocialAccountStatistics, SocialVideo

DEMO = [
    ("Кухня за 60 секунд", "tiktok", "Еда", "Москва", 420_000, 95_000, 1_800_000),
    ("Гаджеты без воды", "youtube", "Технологии", "Россия", 180_000, 40_000, 2_500_000),
    ("Утренний фитнес", "tiktok", "Спорт", "Санкт-Петербург", 75_000, 21_000, 900_000),
    ("Мемы про офис", "tiktok", "Юмор", "Россия", 1_200_000, 310_000, 4_500_000),
    ("Мемы про учёбу", "tiktok", "Юмор", "Россия", 650_000, 150_000, 2_900_000),
    ("Путешествия налегке", "youtube", "Путешествия", "Казань", 95_000, 18_000, 1_200_000),
]


class Command(BaseCommand):
    help = "Create demo sellers, accounts, offers and a network (dev only)"

    def handle(self, *args, **opts):
        if settings.ENV == "production":
            raise CommandError("seed_demo is forbidden in production")
        now = timezone.now()
        sellers = []
        for i in range(2):
            email = f"demo-seller{i + 1}@example.com"
            u = User.objects.filter(email=email).first()
            if not u:
                u = User.objects.create_user(email=email, password="Demo-password-1", is_email_verified=True)
                UserProfile.objects.create(user=u, display_name=f"Демо-продавец {i + 1}")
                assign_role(u, "buyer")
                assign_role(u, "seller")
            sellers.append(u)
        buyer = User.objects.filter(email="demo-buyer@example.com").first()
        if not buyer:
            buyer = User.objects.create_user(email="demo-buyer@example.com", password="Demo-password-1", is_email_verified=True)
            UserProfile.objects.create(user=buyer, display_name="Демо-покупатель")
            assign_role(buyer, "buyer")
        for email, name, role in [("demo-admin@example.com", "Демо-администратор", "admin"),
                                  ("demo-support@example.com", "Демо-поддержка", "support_agent")]:
            if not User.objects.filter(email=email).exists():
                staff = User.objects.create_user(email=email, password="Demo-password-1", is_email_verified=True, is_staff=True)
                UserProfile.objects.create(user=staff, display_name=name)
                assign_role(staff, role)
        created = []
        for n, (title, platform, cat, geo, followers, avg, price) in enumerate(DEMO):
            owner = sellers[0] if n < 4 else sellers[1]
            handle = f"demo_{n}"
            url = f"https://www.tiktok.com/@{handle}" if platform == "tiktok" else f"https://www.youtube.com/@{handle}"
            acc, made = SocialAccount.objects.get_or_create(
                platform=platform, external_id=f"demo-{n}",
                defaults=dict(owner=owner, handle=handle, profile_url=url, title=title, category=cat, geo=geo,
                              description=f"{title}: короткие видео для аудитории {geo}.", is_listed=True))
            if made:
                st = SocialAccountStatistics.objects.create(
                    social_account=acc, followers=followers, avg_views=avg, videos_in_sample=15, source="fake",
                    trust_status="VERIFIED", fetched_at=now, expires_at=now + timedelta(days=30), notes="Демо-данные")
                SocialVideo.objects.bulk_create([SocialVideo(statistics=st, external_video_id=f"{handle}-{k}", url=f"{url}/video/{k}",
                                                             views=avg, published_at=now - timedelta(days=k)) for k in range(15)])
                acc.current_statistics = st
                acc.save()
                AdvertisingOffer.objects.create(social_account=acc, ad_format="integration", price_minor=price,
                                                conditions="Сценарий согласуем до съёмки.")
                AdvertisingOffer.objects.create(social_account=acc, ad_format="mention", price_minor=price // 2)
            created.append(acc)
        net, made = AccountNetwork.objects.get_or_create(owner=sellers[0], title="Сетка юмора", defaults={"description": "Два юмористических канала"})
        if made:
            for acc in created[3:5]:
                acc.owner = sellers[0]
                acc.save()
                NetworkItem.objects.create(network=net, social_account=acc, offer=acc.offers.get(ad_format="integration"),
                                           price_minor=acc.offers.get(ad_format="integration").price_minor)
            net.total_price_minor = 6_500_000
            net.save()
        self.stdout.write(self.style.SUCCESS("Demo data ready. Logins: demo-seller1@, demo-buyer@, demo-admin@, demo-support@example.com — password Demo-password-1"))
