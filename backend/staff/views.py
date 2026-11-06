"""Administration panel API (roadmap Phase 10). Every endpoint checks a specific permission; every change is audited."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User, UserSanction
from audit.models import AuditLog
from audit.services import record, verify_chain
from catalog.models import AccountNetwork
from common.exceptions import DomainError
from common.pagination import StandardPagination
from common.permissions import HasPerm
from orders.models import Order, OrderItem
from payments.models import FinancialLedgerEntry, Payment
from social_data.models import SocialAccount
from support.models import Dispute
from support.services import party_history

ACTIVE = ["AWAITING_SELLER_ACCEPTANCE", "IN_PROGRESS", "AWAITING_PUBLICATION", "PUBLISHED", "AWAITING_BUYER_CONFIRMATION",
          "DISPUTED", "REFUND_PENDING", "PAID"]


def _page(request, qs, view, fn):
    pager = StandardPagination()
    page = pager.paginate_queryset(qs, request, view=view)
    return pager.get_paginated_response([fn(x) for x in page])


class Dashboard(APIView):
    permission_classes = [HasPerm("staff.access")]

    def get(self, request):
        week = timezone.now() - timedelta(days=7)
        data = {
            "users": User.objects.count(),
            "sellers": User.objects.filter(user_roles__role__code="seller").distinct().count(),
            "buyers": User.objects.filter(user_roles__role__code="buyer").distinct().count(),
            "blocked_users": User.objects.filter(status=User.Status.BLOCKED).count(),
            "accounts": SocialAccount.objects.exclude(status="removed").count(),
            "listed_accounts": SocialAccount.objects.filter(is_listed=True, status="active").count(),
            "accounts_under_review": SocialAccount.objects.filter(status="under_review").count(),
            "networks": AccountNetwork.objects.filter(is_active=True).count(),
            "active_orders": Order.objects.filter(status__in=ACTIVE).count(),
            "completed_orders": Order.objects.filter(status="COMPLETED").count(),
            "cancelled_orders": Order.objects.filter(status__in=["CANCELLED", "EXPIRED", "REFUNDED"]).count(),
            "open_disputes": Dispute.objects.exclude(status__in=["RESOLVED", "REJECTED", "CLOSED"]).count(),
            "orders_last_7d": Order.objects.filter(created_at__gte=week).count(),
        }
        if request.user.has_perm_code("finance.view"):
            # Only provider-confirmed operations (roadmap 10.1): succeeded payments/refunds/payouts from the journal
            def s(kind):
                return FinancialLedgerEntry.objects.filter(kind=kind).aggregate(v=Sum("amount_minor"))["v"] or 0

            data["finance"] = {
                "payments_minor": Payment.objects.filter(status="succeeded").aggregate(v=Sum("amount_minor"))["v"] or 0,
                "refunds_minor": s("refund_succeeded"), "payouts_paid_minor": s("payout_paid"), "platform_fee_minor": s("platform_fee"),
                "provider": Payment.objects.values_list("provider", flat=True).first() or "mock",
            }
        return Response(data)


# --- users ---------------------------------------------------------------------------------
def _user_row(u):
    return {"id": str(u.pk), "email": u.email, "display_name": getattr(getattr(u, "profile", None), "display_name", ""),
            "status": u.status, "roles": sorted(u.role_codes), "is_email_verified": u.is_email_verified,
            "date_joined": u.date_joined, "last_seen_at": u.last_seen_at}


class Users(APIView):
    permission_classes = [HasPerm("staff.view_personal_data")]

    def get(self, request):
        qs = User.objects.select_related("profile").order_by("-date_joined")
        if q := (request.query_params.get("q") or "").strip():
            qs = qs.filter(Q(email__icontains=q) | Q(profile__display_name__icontains=q))
        if st := request.query_params.get("status"):
            qs = qs.filter(status=st)
        record(action="staff.users_search", subject_type="user", subject_id="*", actor=request.user, is_staff_action=True,
               after={"q": request.query_params.get("q") or ""})
        return _page(request, qs, self, _user_row)


class UserDetail(APIView):
    permission_classes = [HasPerm("staff.view_personal_data")]

    def get(self, request, pk):
        u = get_object_or_404(User.objects.select_related("profile"), pk=pk)
        record(action="staff.user_viewed", subject_type="user", subject_id=u.pk, actor=request.user, is_staff_action=True)
        return Response({
            **_user_row(u),
            "orders_as_buyer": list(Order.objects.filter(buyer=u).order_by("-created_at").values("id", "status", "total_minor", "created_at")[:50]),
            "orders_as_seller": list(Order.objects.filter(seller=u).order_by("-created_at").values("id", "status", "total_minor", "created_at")[:50]),
            "disputes": party_history(u.pk),
            "sanctions": list(u.sanctions.order_by("-created_at").values("id", "type", "reason", "starts_at", "ends_at", "revoked_at")),
            "accounts": list(SocialAccount.objects.filter(owner=u).values("id", "platform", "handle", "status", "is_listed")),
            "history": list(AuditLog.objects.filter(Q(actor=u) | Q(subject_type="user", subject_id=str(u.pk))).order_by("-seq")
                            .values("action", "created_at", "actor_id")[:100]),
        })


class UserSanctionAction(APIView):
    permission_classes = [HasPerm("user.sanction")]

    def post(self, request, pk, action):
        u = get_object_or_404(User, pk=pk)
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 5:
            raise DomainError("Укажите основание", code="reason_required", status_code=400)
        if u.pk == request.user.pk:
            raise DomainError("Нельзя применить к себе", code="self_action", status_code=400)
        if u.has_perm_code("staff.access") and not request.user.has_perm_code("user.manage_roles"):
            raise DomainError("Санкции к сотрудникам применяет супер-администратор", code="forbidden", status_code=403)
        before = u.status
        with transaction.atomic():
            if action in ("warning", "limit", "block"):
                days = request.data.get("days")
                UserSanction.objects.create(user=u, type=action, reason=reason, created_by=request.user,
                                            ends_at=timezone.now() + timedelta(days=int(days)) if days else None)
                if action == "block":
                    u.status = User.Status.BLOCKED
                elif action == "limit":
                    u.status = User.Status.LIMITED
            elif action == "unblock":
                u.status = User.Status.ACTIVE
                u.sanctions.filter(revoked_at__isnull=True, type__in=["block", "limit"]).update(revoked_at=timezone.now())
            else:
                raise DomainError("Неизвестное действие", code="bad_action", status_code=404)
            u.save(update_fields=["status", "updated_at"])
            record(action=f"user.{action}", subject_type="user", subject_id=u.pk, actor=request.user, is_staff_action=True,
                   before={"status": before}, after={"status": u.status}, reason=reason)
        return Response(_user_row(u))


# --- social accounts --------------------------------------------------------------------------
def _acc_row(a):
    st = a.current_statistics
    return {"id": str(a.pk), "platform": a.platform, "handle": a.handle, "title": a.title, "status": a.status, "is_listed": a.is_listed,
            "owner": a.owner.email, "ownership_verified": a.ownership_verified,
            "followers": st.followers if st else None, "avg_views": st.avg_views if st else None,
            "trust_status": st.trust_status if st else None, "fetched_at": st.fetched_at if st else None}


class Accounts(APIView):
    permission_classes = [HasPerm("moderation.stats")]

    def get(self, request):
        qs = SocialAccount.objects.select_related("owner", "current_statistics").order_by("-created_at")
        p = request.query_params
        if st := p.get("status"):
            qs = qs.filter(status=st)
        if t := p.get("trust"):
            qs = qs.filter(current_statistics__trust_status=t)
        if q := (p.get("q") or "").strip():
            qs = qs.filter(Q(handle__icontains=q) | Q(title__icontains=q) | Q(owner__email__icontains=q))
        return _page(request, qs, self, _acc_row)


class AccountDetail(APIView):
    permission_classes = [HasPerm("moderation.stats")]

    def get(self, request, pk):
        a = get_object_or_404(SocialAccount.objects.select_related("owner", "current_statistics"), pk=pk)
        return Response({**_acc_row(a),
                         "history": list(a.statistics.order_by("-fetched_at").values("followers", "avg_views", "videos_in_sample",
                                                                                     "trust_status", "source", "fetched_at", "notes")[:50]),
                         "jobs": list(a.refresh_jobs.order_by("-created_at").values("trigger", "status", "error_code", "created_at")[:50]),
                         "orders": list(OrderItem.objects.filter(social_account=a).values("order_id", "status", "price_minor")[:50])})


class AccountModeration(APIView):
    permission_classes = [HasPerm("moderation.stats")]

    def post(self, request, pk, action):
        a = get_object_or_404(SocialAccount, pk=pk)
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 5:
            raise DomainError("Укажите основание", code="reason_required", status_code=400)
        before = {"status": a.status, "is_listed": a.is_listed}
        if action == "hide":
            a.is_listed = False
        elif action == "review":
            a.status, a.is_listed = SocialAccount.Status.UNDER_REVIEW, False
        elif action == "approve":
            a.status = SocialAccount.Status.ACTIVE
            st = a.current_statistics
            if st and st.trust_status == "SUSPICIOUS":
                st.trust_status = "VERIFIED" if st.source == "official_api" else "MANUAL"
                st.notes = (st.notes + f"\nПроверено модератором: {reason}").strip()
                st.save(update_fields=["trust_status", "notes", "updated_at"])
        elif action == "block":
            a.status, a.is_listed = SocialAccount.Status.BLOCKED, False
        elif action == "recheck":
            from social_data.services.refresh_service import request_refresh

            request_refresh(a.pk, user=request.user, trigger="admin_check")
        else:
            raise DomainError("Неизвестное действие", code="bad_action", status_code=404)
        a.save()
        record(action=f"social_account.{action}", subject_type="social_account", subject_id=a.pk, actor=request.user,
               is_staff_action=True, before=before, after={"status": a.status, "is_listed": a.is_listed}, reason=reason)
        a.refresh_from_db()
        return Response(_acc_row(a))


# --- orders -----------------------------------------------------------------------------------
class Orders(APIView):
    permission_classes = [HasPerm("staff.view_orders")]

    def get(self, request):
        qs = Order.objects.select_related("buyer", "seller").annotate(n=Count("items")).order_by("-created_at")
        p = request.query_params
        if st := p.get("status"):
            qs = qs.filter(status__in=st.split(","))
        if q := (p.get("q") or "").strip():
            import uuid

            try:
                qs = qs.filter(pk=uuid.UUID(q))
            except ValueError:
                qs = qs.filter(Q(buyer__email__icontains=q) | Q(seller__email__icontains=q))
        if p.get("disputed") == "1":
            qs = qs.filter(disputes__isnull=False).distinct()
        return _page(request, qs, self, lambda o: {
            "id": str(o.pk), "status": o.status, "total_minor": o.total_minor, "created_at": o.created_at, "paid_at": o.paid_at,
            "buyer": o.buyer.email, "seller": o.seller.email, "items": o.n,
            "payment": o.payments.filter(status="succeeded").values_list("status", flat=True).first() or (o.payments.values_list("status", flat=True).first())})


# --- audit -------------------------------------------------------------------------------------
class Audit(APIView):
    permission_classes = [HasPerm("audit.view")]

    def get(self, request):
        qs = AuditLog.objects.select_related("actor").order_by("-seq")
        p = request.query_params
        if p.get("staff") == "1":
            qs = qs.filter(is_staff_action=True)
        if a := p.get("action"):
            qs = qs.filter(action__startswith=a)
        if o := p.get("order"):
            qs = qs.filter(order_id=o)
        if actor := p.get("actor"):
            qs = qs.filter(actor__email__icontains=actor)
        return _page(request, qs, self, lambda e: {
            "seq": e.seq, "action": e.action, "actor": e.actor.email if e.actor else "system", "subject_type": e.subject_type,
            "subject_id": e.subject_id, "order_id": str(e.order_id) if e.order_id else None, "before": e.before, "after": e.after,
            "reason": e.reason, "comment": e.comment, "created_at": e.created_at, "is_staff_action": e.is_staff_action})


class AuditVerify(APIView):
    permission_classes = [HasPerm("audit.view")]

    def get(self, request):
        ok, broken = verify_chain()
        return Response({"ok": ok, "first_broken_seq": broken, "entries": AuditLog.objects.count()})
