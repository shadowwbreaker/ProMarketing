"""Anti-fraud signals (roadmap Phase 12). Signals are prompts for a human review — they never punish anyone
automatically and are not shown to other users."""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from chats.models import ChatMessage
from orders.models import OrderEvent, PublicationProof
from reviews.models import Review
from social_data.models import SocialAccount
from support.models import Dispute, DisputeDecision

THRESHOLDS = {
    "rejected_complaints": 3,      # repeated false complaints (scenario 7)
    "missed_deadlines": 3,         # repeated deadline breaches
    "contact_messages": 3,         # attempts to move the deal off-platform (scenario 10)
    "reviews_from_one_buyer": 3,   # possible review manipulation
    "young_reviewer_days": 7,
}


def collect(now=None) -> list[dict]:
    now = now or timezone.now()
    out: list[dict] = []

    for a in SocialAccount.objects.filter(current_statistics__trust_status="SUSPICIOUS").select_related("owner", "current_statistics"):
        out.append({"type": "suspicious_stats", "severity": "high", "user": str(a.owner_id), "subject": f"social_account:{a.pk}",
                    "detail": a.current_statistics.notes or "резкий рост статистики"})

    rejected = (DisputeDecision.objects.filter(decision_type="reject").values("dispute__opened_by")
                .annotate(n=Count("dispute", distinct=True)).filter(n__gte=THRESHOLDS["rejected_complaints"]))
    for r in rejected:
        out.append({"type": "repeated_false_complaints", "severity": "medium", "user": str(r["dispute__opened_by"]),
                    "subject": f"user:{r['dispute__opened_by']}", "detail": f"отклонённых жалоб: {r['n']}"})

    missed = (OrderEvent.objects.filter(type="item.publish_deadline_missed").values("order__seller")
              .annotate(n=Count("id")).filter(n__gte=THRESHOLDS["missed_deadlines"]))
    for m in missed:
        out.append({"type": "repeated_missed_deadlines", "severity": "medium", "user": str(m["order__seller"]),
                    "subject": f"user:{m['order__seller']}", "detail": f"пропущенных сроков: {m['n']}"})

    contacts = (ChatMessage.objects.filter(contact_signal=True).values("author")
                .annotate(n=Count("id")).filter(n__gte=THRESHOLDS["contact_messages"]))
    for c in contacts:
        out.append({"type": "off_platform_attempts", "severity": "high", "user": str(c["author"]), "subject": f"user:{c['author']}",
                    "detail": f"сообщений с контактами/реквизитами: {c['n']}"})

    pairs = (Review.objects.filter(moderation_status="published").values("author", "target_user")
             .annotate(n=Count("id")).filter(n__gte=THRESHOLDS["reviews_from_one_buyer"]))
    for p in pairs:
        out.append({"type": "review_manipulation", "severity": "medium", "user": str(p["target_user"]),
                    "subject": f"user:{p['target_user']}", "detail": f"{p['n']} отзывов от одного покупателя"})
    young = (Review.objects.filter(moderation_status="published", rating=5,
                                   author__date_joined__gte=now - timedelta(days=THRESHOLDS["young_reviewer_days"]))
             .values("target_user").annotate(n=Count("id")).filter(n__gte=3))
    for y in young:
        out.append({"type": "review_manipulation", "severity": "low", "user": str(y["target_user"]), "subject": f"user:{y['target_user']}",
                    "detail": f"{y['n']} пятёрок от новых аккаунтов"})

    changed = (PublicationProof.objects.values("order_item").annotate(urls=Count("video_url", distinct=True)).filter(urls__gt=1))
    for ch in changed:
        out.append({"type": "proof_link_changed", "severity": "medium", "user": None, "subject": f"order_item:{ch['order_item']}",
                    "detail": f"ссылка на публикацию менялась ({ch['urls']} разных)"})

    open_by_seller = (Dispute.objects.exclude(status__in=["RESOLVED", "REJECTED", "CLOSED"]).values("order__seller")
                      .annotate(n=Count("id")).filter(n__gte=3))
    for o in open_by_seller:
        out.append({"type": "many_open_disputes", "severity": "medium", "user": str(o["order__seller"]),
                    "subject": f"user:{o['order__seller']}", "detail": f"открытых жалоб на продавца: {o['n']}"})
    return out



