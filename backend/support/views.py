from common.throttles import ScopedRateThrottle
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from audit.services import record
from common.exceptions import DomainError
from common.pagination import StandardPagination
from common.permissions import HasPerm, IsActiveUser
from orders.models import Order

from . import services
from .models import ACTIVE_DISPUTE_STATUSES, AdminNote, Dispute, DisputeReason


# --- serialization ----------------------------------------------------------------------
def _msg(m, staff):
    return {"id": str(m.pk), "author": str(m.author_id), "author_name": m.author.profile.display_name if hasattr(m.author, "profile") else "",
            "is_staff": m.author.has_perm_code("staff.access"), "visibility": m.visibility, "body": m.body, "created_at": m.created_at}


def dispute_payload(d: Dispute, *, staff: bool) -> dict:
    msgs = d.messages.select_related("author__profile").order_by("created_at")
    if not staff:
        msgs = msgs.filter(visibility="all")
    data = {
        "id": str(d.pk), "order": str(d.order_id), "status": d.status, "priority": d.priority,
        "reason": {"code": d.reason.code, "title": d.reason.title}, "description": d.description,
        "opened_by": str(d.opened_by_id), "opened_by_role": "buyer" if d.opened_by_id == d.order.buyer_id else "seller",
        "assignee": str(d.assignee_id) if d.assignee_id else None, "response_due_at": d.response_due_at,
        "response_overdue": d.response_overdue, "has_counterclaim": d.has_counterclaim, "created_at": d.created_at,
        "resolved_at": d.resolved_at, "appeal_of": str(d.appeal_of_id) if d.appeal_of_id else None,
        "items": [{"order_item": str(i.order_item_id), "status_before": i.status_before, "active": i.is_active,
                   "account": i.order_item.social_account.title, "price_minor": i.order_item.price_minor}
                  for i in d.items.select_related("order_item__social_account")],
        "messages": [_msg(m, staff) for m in msgs],
        "evidence": [{"id": str(e.pk), "submitted_by": str(e.submitted_by_id), "url": e.url, "description": e.description,
                      "attachment": str(e.attachment_id) if e.attachment_id else None, "sha256": e.sha256, "created_at": e.created_at}
                     for e in d.evidence.order_by("created_at")],
        "decisions": [{"id": str(x.pk), "item": str(x.order_item_id) if x.order_item_id else None, "type": x.decision_type,
                       "comment": x.comment, "refund_amount_minor": x.refund_amount_minor, "created_at": x.created_at,
                       "actions": [{"type": a.action_type, "status": a.status, "error": a.error} for a in x.actions.all()]}
                      for x in d.decisions.order_by("created_at")],
    }
    return data


def staff_dispute_detail(d: Dispute) -> dict:
    """Everything an arbiter needs on one screen (roadmap 9.8)."""
    from chats.models import ChatMessage
    from orders.models import OrderEvent, PublicationCheck
    from orders.views import ItemSerializer, TermsSerializer
    from payments.models import FinancialLedgerEntry, Payment, Payout
    from payments.providers.registry import get_payment_provider
    from payments.services import refunded_amount

    o = d.order
    data = dispute_payload(d, staff=True)
    caps = get_payment_provider().capabilities
    items = o.items.select_related("social_account__current_statistics", "offer", "order")
    data["order"] = {
        "id": str(o.pk), "status": o.status, "total_minor": o.total_minor, "created_at": o.created_at, "paid_at": o.paid_at,
        "buyer": {"id": str(o.buyer_id), "name": o.buyer.profile.display_name, "email": o.buyer.email, "history": services.party_history(o.buyer_id)},
        "seller": {"id": str(o.seller_id), "name": o.seller.profile.display_name, "email": o.seller.email, "history": services.party_history(o.seller_id),
                   "last_seen_at": o.seller.last_seen_at},
        "original_terms": TermsSerializer(o.terms_versions.order_by("version").first()).data,
        "current_terms": TermsSerializer(o.current_terms_version).data,
        "items": ItemSerializer(items, many=True, context={"staff": True}).data,
    }
    data["chat"] = [{"kind": m.kind, "author": str(m.author_id) if m.author_id else None, "body": m.body, "deleted_at": m.deleted_at,
                     "revision": m.revision, "contact_signal": m.contact_signal, "created_at": m.created_at,
                     "attachments": [str(a.pk) for a in m.attachments.all()]}
                    for m in ChatMessage.objects.filter(chat__order=o).order_by("created_at").prefetch_related("attachments")]
    data["events"] = list(OrderEvent.objects.filter(order=o).order_by("seq").values("seq", "type", "order_item", "from_status", "to_status", "payload", "created_at"))
    data["publication_checks"] = list(PublicationCheck.objects.filter(order_item__order=o).values("order_item", "trigger", "result", "checked_at"))
    data["account_stats"] = [{"item": str(i.pk), "account": str(i.social_account_id),
                              "history": list(i.social_account.statistics.order_by("-fetched_at").values(
                                  "followers", "avg_views", "videos_in_sample", "trust_status", "source", "fetched_at")[:10])} for i in items]
    data["payment"] = {
        "payments": list(Payment.objects.filter(order=o).values("id", "status", "amount_minor", "provider", "succeeded_at")),
        "payouts": list(Payout.objects.filter(order_item__order=o).values("order_item", "status", "amount_minor", "available_at")),
        "refundable": {str(i.pk): i.price_minor - refunded_amount(i.pk) for i in items},
        "ledger": list(FinancialLedgerEntry.objects.filter(order_item__order=o).order_by("created_at").values("kind", "amount_minor", "order_item", "created_at")),
        "provider_capabilities": {"partial_refund": caps.partial_refund, "refund_before_payout": caps.refund_before_payout,
                                  "pause_payout_on_dispute": caps.pause_payout_on_dispute},
    }
    data["previous_disputes"] = list(Dispute.objects.filter(Q(order__buyer_id=o.buyer_id) | Q(order__seller_id=o.seller_id))
                                     .exclude(pk=d.pk).values("id", "order", "status", "reason__code", "created_at")[:20])
    data["referred_at"] = d.referred_at
    data["admin_notes"] = list(AdminNote.objects.filter(subject_type="dispute", subject_id=d.pk).order_by("created_at")
                               .values("id", "author", "body", "created_at"))
    return data


# --- party endpoints ---------------------------------------------------------------------
class Reasons(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        return Response(list(DisputeReason.objects.filter(is_active=True).values("code", "title", "allowed_for")))


class EvidenceIn(serializers.Serializer):
    attachment = serializers.UUIDField(required=False)
    url = serializers.URLField(required=False, max_length=1000)
    description = serializers.CharField(required=False, allow_blank=True, max_length=4000)


class OpenIn(serializers.Serializer):
    items = serializers.ListField(child=serializers.UUIDField(), required=False)
    reason = serializers.CharField(max_length=48)
    description = serializers.CharField(max_length=10_000)
    evidence = EvidenceIn(many=True, required=False)


class OpenDispute(APIView):
    permission_classes = [IsActiveUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "dispute_open"

    def post(self, request, pk):
        s = OpenIn(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        d = services.open_dispute(pk, actor=request.user, item_ids=v.get("items") or [], reason_code=v["reason"],
                                  description=v["description"], evidence=[dict(e) for e in v.get("evidence", [])])
        return Response(dispute_payload(Dispute.objects.get(pk=d.pk), staff=False), status=201)


class OrderDisputes(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, pk):
        o = get_object_or_404(Order, pk=pk)
        if request.user.pk not in (o.buyer_id, o.seller_id) and not request.user.has_perm_code("dispute.handle"):
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        return Response([dispute_payload(d, staff=False) for d in o.disputes.order_by("-created_at")])


def _party_dispute(request, pk) -> Dispute:
    d = get_object_or_404(Dispute.objects.select_related("order", "reason"), pk=pk)
    if request.user.pk not in (d.order.buyer_id, d.order.seller_id):
        raise DomainError("Нет доступа", code="forbidden", status_code=404)
    return d


class DisputeDetail(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, pk):
        return Response(dispute_payload(_party_dispute(request, pk), staff=False))


class ReplyIn(serializers.Serializer):
    body = serializers.CharField(required=False, allow_blank=True, max_length=10_000)
    evidence = EvidenceIn(many=True, required=False)


class Reply(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, pk):
        _party_dispute(request, pk)
        s = ReplyIn(data=request.data)
        s.is_valid(raise_exception=True)
        services.party_reply(pk, actor=request.user, body=s.validated_data.get("body", ""),
                             evidence=[dict(e) for e in s.validated_data.get("evidence", [])])
        return Response(dispute_payload(Dispute.objects.get(pk=pk), staff=False))


class AppealIn(serializers.Serializer):
    reason = serializers.CharField(min_length=20, max_length=10000)


class Appeal(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, pk):
        _party_dispute(request, pk)
        form = AppealIn(data=request.data)
        form.is_valid(raise_exception=True)
        a = services.appeal(pk, actor=request.user, reason=form.validated_data["reason"])
        return Response(dispute_payload(a, staff=False), status=201)


# --- staff endpoints -------------------------------------------------------------------
class StaffQueue(APIView):
    permission_classes = [HasPerm("dispute.handle")]

    def get(self, request):
        qs = Dispute.objects.filter(referred_at__isnull=True).select_related(
            "order__buyer__profile", "order__seller__profile", "reason", "assignee",
        )
        p = request.query_params
        if s := p.get("status"):
            qs = qs.filter(status__in=s.split(","))
        else:
            qs = qs.exclude(status="CLOSED")
        if pr := p.get("priority"):
            qs = qs.filter(priority=pr)
        if p.get("assignee") == "me":
            qs = qs.filter(assignee=request.user)
        elif p.get("assignee") == "none":
            qs = qs.filter(assignee__isnull=True)
        if r := p.get("reason"):
            qs = qs.filter(reason__code=r)
        qs = qs.order_by("-priority", "created_at")  # high first, oldest first
        pager = StandardPagination()
        page = pager.paginate_queryset(qs, request, view=self)
        return pager.get_paginated_response([{
            "id": str(d.pk), "status": d.status, "priority": d.priority, "created_at": d.created_at, "order": str(d.order_id),
            "amount_minor": d.order.total_minor, "buyer": d.order.buyer.profile.display_name, "seller": d.order.seller.profile.display_name,
            "reason": d.reason.title, "assignee": d.assignee.email if d.assignee else None, "response_overdue": d.response_overdue,
            "is_appeal": bool(d.appeal_of_id), "has_counterclaim": d.has_counterclaim} for d in page])


class ArbitrationQueue(APIView):
    permission_classes = [HasPerm("arbitration.work")]

    def get(self, request):
        qs = Dispute.objects.filter(referred_at__isnull=False).exclude(
            Q(order__buyer=request.user) | Q(order__seller=request.user),
        ).select_related("reason")
        if request.query_params.get("scope") == "mine":
            qs = qs.filter(assignee=request.user)
        else:
            qs = qs.filter(assignee__isnull=True, status__in=ACTIVE_DISPUTE_STATUSES)
        pager = StandardPagination()
        page = pager.paginate_queryset(qs.order_by("referred_at", "pk"), request, view=self)
        return pager.get_paginated_response([{
            "id": str(d.pk), "order_number": str(d.order_id)[:8], "reason": d.reason.title,
            "status": d.get_status_display(), "referred_at": d.referred_at,
        } for d in page])


class ArbitrationClaim(APIView):
    permission_classes = [HasPerm("arbitration.work")]

    def post(self, request, pk):
        get_object_or_404(Dispute, pk=pk, referred_at__isnull=False)
        dispute = services.assign(pk, actor=request.user, assignee=request.user)
        return Response({"id": str(dispute.pk)})


def require_case_access(dispute, user):
    services._staff(dispute, user)
    if not (dispute.referred_at and user.has_perm_code("arbitration.work") and dispute.assignee_id == user.pk):
        raise DomainError("Карточка доступна назначенному арбитру", code="arbitration_required", status_code=403)


class StaffDetail(APIView):
    permission_classes = [HasPerm("dispute.handle", "staff.view_personal_data")]

    def get(self, request, pk):
        d = get_object_or_404(Dispute.objects.select_related("order__buyer__profile", "order__seller__profile", "reason"), pk=pk)
        require_case_access(d, request.user)
        record(action="dispute.viewed", subject_type="dispute", subject_id=d.pk, actor=request.user, is_staff_action=True, order_id=d.order_id)
        return Response(staff_dispute_detail(d))


class StaffAction(APIView):
    permission_classes = [HasPerm("dispute.handle")]

    def post(self, request, pk, action):
        u, data = request.user, request.data
        dispute = get_object_or_404(Dispute, pk=pk)
        require_case_access(dispute, u)
        if action == "close":
            comment = serializers.CharField(min_length=10, max_length=10000).run_validation(data.get("comment"))
            services.close_without_refund(pk, actor=u, comment=comment)
        elif action == "assign":
            assignee = get_object_or_404(User, pk=data.get("assignee") or u.pk)
            services.assign(pk, actor=u, assignee=assignee)
        elif action == "priority":
            services.set_priority(pk, actor=u, priority=data.get("priority", ""))
        elif action == "message":
            services.staff_message(pk, actor=u, body=data.get("body", ""), internal=bool(data.get("internal")))
        elif action == "request-evidence":
            services.request_evidence(pk, actor=u, from_party=data.get("from", ""), comment=data.get("comment", ""), hours=data.get("hours"))
        elif action == "escalate":
            services.escalate(pk, actor=u, comment=data.get("comment", ""))
        elif action == "decide":
            from django.utils.dateparse import parse_datetime

            nd = parse_datetime(data["new_deadline"]) if data.get("new_deadline") else None
            services.decide(pk, actor=u, item_id=data.get("item"), decision_type=data.get("decision", ""), comment=data.get("comment", ""),
                            refund_amount_minor=data.get("refund_amount_minor"), new_deadline=nd, sanction=data.get("sanction"))
        elif action == "note":
            d = get_object_or_404(Dispute, pk=pk)
            AdminNote.objects.create(subject_type="dispute", subject_id=d.pk, author=u, body=(data.get("body") or "")[:10_000])
            record(action="dispute.note", subject_type="dispute", subject_id=d.pk, actor=u, is_staff_action=True, order_id=d.order_id)
        elif action == "check-publication":
            from orders.tasks import check_publication

            d = get_object_or_404(Dispute, pk=pk)
            item = get_object_or_404(d.order.items, pk=data.get("item"))
            check_publication.delay(str(item.pk), "admin", str(u.pk))
            record(action="dispute.publication_check", subject_type="dispute", subject_id=d.pk, actor=u, is_staff_action=True, order_id=d.order_id)
        elif action == "check-account":
            from social_data.services.refresh_service import request_refresh

            d = get_object_or_404(Dispute, pk=pk)
            item = get_object_or_404(d.order.items, pk=data.get("item"))
            request_refresh(item.social_account_id, user=u, trigger="admin_check")  # scenarios 8 and 12
        else:
            raise DomainError("Неизвестное действие", code="bad_action", status_code=404)
        d = Dispute.objects.select_related("order__buyer__profile", "order__seller__profile", "reason").get(pk=pk)
        return Response(staff_dispute_detail(d))
