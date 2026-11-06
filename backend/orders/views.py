from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import DomainError
from common.permissions import HasPerm, IsActiveUser, IsEmailVerified
from payments.models import Payout

from . import services
from .models import Order, OrderEvent, OrderItem, OrderTermsVersion, PublicationCheck


class TermsInSerializer(serializers.Serializer):
    brand = serializers.CharField(max_length=200)
    site_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    brief = serializers.CharField(max_length=10_000)
    ad_text = serializers.CharField(max_length=5_000, required=False, allow_blank=True)
    cta = serializers.CharField(max_length=300, required=False, allow_blank=True)
    links = serializers.ListField(child=serializers.URLField(max_length=500), required=False, max_length=10)
    publish_deadline = serializers.DateTimeField(required=False, allow_null=True)
    placement_days = serializers.IntegerField(min_value=1, max_value=365, required=False)
    extra_requirements = serializers.CharField(max_length=5_000, required=False, allow_blank=True)
    materials_deadline = serializers.DateTimeField(required=False, allow_null=True)
    platform_removal_policy = serializers.ChoiceField(choices=["refund_or_repeat", "seller_not_liable", "full_refund"], required=False)


class CreateOrderSerializer(serializers.Serializer):
    offer = serializers.UUIDField(required=False)
    network = serializers.UUIDField(required=False)
    network_items = serializers.ListField(child=serializers.UUIDField(), required=False)
    terms = TermsInSerializer()

    def validate(self, attrs):
        if bool(attrs.get("offer")) == bool(attrs.get("network")):
            raise serializers.ValidationError("Укажите либо предложение, либо сетку")
        return attrs


class TermsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTermsVersion
        exclude = ["order", "proposed_by"]


class ItemSerializer(serializers.ModelSerializer):
    account = serializers.SerializerMethodField()
    proofs = serializers.SerializerMethodField()
    payout = serializers.SerializerMethodField()
    refunded_minor = serializers.SerializerMethodField()
    checks = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "status", "price_minor", "fee_minor", "seller_amount_minor", "accept_deadline", "publish_deadline",
                  "placement_until", "accepted_at", "published_at", "confirm_deadline", "confirmed_at", "payout_available_at",
                  "account", "proofs", "payout", "refunded_minor", "checks", "review"]

    def get_account(self, o):
        a = o.social_account
        return {"id": str(a.pk), "platform": a.platform, "handle": a.handle, "title": a.title, "profile_url": a.profile_url,
                "ad_format": o.offer.ad_format, "ad_format_label": o.offer.get_ad_format_display()}

    def get_proofs(self, o):
        return [{"id": str(p.pk), "video_url": p.video_url, "published_at": p.published_at, "notes": p.notes, "created_at": p.created_at}
                for p in o.proofs.order_by("created_at")]

    def get_payout(self, o):
        po = Payout.objects.filter(order_item=o).first()
        if not po or self.context.get("viewer_id") not in (o.order.seller_id, None) and not self.context.get("staff"):
            return None if not po else {"status": po.status, "available_at": po.available_at}
        return {"id": str(po.pk), "status": po.status, "amount_minor": po.amount_minor, "available_at": po.available_at}

    def get_refunded_minor(self, o):
        from payments.services import refunded_amount

        return refunded_amount(o.pk, include_pending=False)

    def get_review(self, o):
        r = o.reviews.first()
        return None if not r else {"id": str(r.pk), "rating": r.rating, "text": r.text, "seller_reply": r.seller_reply,
                                   "moderation_status": r.moderation_status}

    def get_checks(self, o):
        return [{"trigger": c.trigger, "result": c.result, "checked_at": c.checked_at} for c in o.publication_checks.order_by("-checked_at")[:5]]


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    terms = TermsSerializer(source="current_terms_version")
    buyer = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    proposals = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ["id", "status", "total_minor", "currency", "fee_bps", "created_at", "paid_at", "materials_delivered_at",
                  "seller_terms_accepted_at", "network", "items", "terms", "buyer", "seller", "role", "proposals"]

    def get_items(self, o):
        return ItemSerializer(o.items.select_related("social_account", "offer", "order").order_by("created_at"), many=True,
                              context=self.context).data

    def _party(self, u):
        return {"id": str(u.pk), "display_name": u.profile.display_name, "last_seen_at": u.last_seen_at}

    def get_buyer(self, o):
        return self._party(o.buyer)

    def get_seller(self, o):
        return self._party(o.seller)

    def get_role(self, o):
        vid = self.context.get("viewer_id")
        return "buyer" if vid == o.buyer_id else "seller" if vid == o.seller_id else "staff"

    def get_proposals(self, o):
        return [{"id": str(p.pk), "changes": p.changes, "comment": p.comment, "status": p.status,
                 "proposed_by": str(p.proposed_by_id), "created_at": p.created_at} for p in o.terms_proposals.order_by("-created_at")[:10]]


def _order_for(request, pk) -> Order:
    """Participants only; staff with staff.view_orders can read (roadmap 8.1: administration in disputes)."""
    u = request.user
    qs = Order.objects.select_related("buyer__profile", "seller__profile", "current_terms_version")
    if u.has_perm_code("staff.view_orders"):
        return get_object_or_404(qs, pk=pk)
    return get_object_or_404(qs.filter(Q(buyer=u) | Q(seller=u)), pk=pk)


def _out(request, order):
    order.refresh_from_db()
    ctx = {"viewer_id": request.user.pk, "staff": request.user.has_perm_code("staff.view_orders")}
    return Response(OrderSerializer(order, context=ctx).data)


class OrderCreate(APIView):
    permission_classes = [HasPerm("order.create"), IsEmailVerified]

    @extend_schema(request=CreateOrderSerializer, responses={201: OrderSerializer})
    def post(self, request):
        s = CreateOrderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        order = services.create_order(buyer=request.user, terms=d["terms"], offer_id=d.get("offer"),
                                      network_id=d.get("network"), network_item_ids=d.get("network_items"))
        r = _out(request, order)
        r.status_code = 201
        return r


class OrderDetail(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, pk):
        return _out(request, _order_for(request, pk))


class OrderEvents(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, pk):
        order = _order_for(request, pk)
        evs = OrderEvent.objects.filter(order=order).order_by("seq")
        return Response([{"seq": e.seq, "type": e.type, "item": str(e.order_item_id) if e.order_item_id else None,
                          "from": e.from_status, "to": e.to_status, "payload": e.payload, "created_at": e.created_at,
                          "actor": str(e.actor_id) if e.actor_id else None} for e in evs])


class OrderTermsHistory(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, pk):
        order = _order_for(request, pk)
        return Response(TermsSerializer(order.terms_versions.order_by("version"), many=True).data)


class _Action(APIView):
    permission_classes = [IsActiveUser]

    def run(self, request, pk, item_id):  # pragma: no cover
        raise NotImplementedError

    def post(self, request, pk, item_id=None):
        self.run(request, pk, item_id)
        return _out(request, Order.objects.get(pk=pk))


class Accept(_Action):
    def run(self, request, pk, item_id):
        services.accept_item(pk, item_id, actor=request.user)


class Decline(_Action):
    def run(self, request, pk, item_id):
        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 3:
            raise DomainError("Укажите причину отказа", code="reason_required", status_code=400)
        services.decline_item(pk, item_id, actor=request.user, reason=reason)


class ReadyForPublication(_Action):
    def run(self, request, pk, item_id):
        services.mark_awaiting_publication(pk, item_id, actor=request.user)


class ProofSerializer(serializers.Serializer):
    video_url = serializers.URLField(max_length=500)
    published_at = serializers.DateTimeField()
    notes = serializers.CharField(max_length=4000, required=False, allow_blank=True)


class SubmitProof(_Action):
    def run(self, request, pk, item_id):
        s = ProofSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.submit_proof(pk, item_id, actor=request.user, **s.validated_data)


class Confirm(_Action):
    def run(self, request, pk, item_id):
        services.confirm_item(pk, item_id, actor=request.user)


class Rework(_Action):
    def run(self, request, pk, item_id):
        services.request_rework(pk, item_id, actor=request.user, comment=(request.data.get("comment") or "")[:2000])


class CancelItem(_Action):
    def run(self, request, pk, item_id):
        services.cancel_before_acceptance(pk, item_id, actor=request.user)


class CancelUnpaid(_Action):
    def run(self, request, pk, item_id):
        services.cancel_unpaid(pk, actor=request.user)


class MaterialsDelivered(_Action):
    def run(self, request, pk, item_id):
        services.mark_materials_delivered(pk, actor=request.user)


class CheckPublication(_Action):
    """Buyer-triggered one-off check (D-010), limited per item."""

    def run(self, request, pk, item_id):
        from .tasks import check_publication

        order = _order_for(request, pk)
        if order.buyer_id != request.user.pk:
            raise DomainError("Нет доступа", code="forbidden", status_code=403)
        item = get_object_or_404(order.items, pk=item_id)
        if not item.proofs.exists():
            raise DomainError("Продавец ещё не прислал ссылку на публикацию", code="no_proof")
        used = PublicationCheck.objects.filter(order_item=item, trigger=PublicationCheck.Trigger.BUYER).count()
        if used >= settings.BUYER_PUBLICATION_CHECKS_LIMIT:
            raise DomainError("Лимит проверок публикации исчерпан", code="checks_limit", status_code=429)
        check_publication.delay(str(item.pk), PublicationCheck.Trigger.BUYER, str(request.user.pk))


class ProposeTerms(_Action):
    def run(self, request, pk, item_id):
        services.propose_terms(pk, actor=request.user, changes=request.data.get("changes") or {},
                               comment=(request.data.get("comment") or "")[:2000])


class DecideTerms(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, pk, proposal_id):
        services.decide_terms(pk, proposal_id, actor=request.user, accept=bool(request.data.get("accept")))
        return _out(request, Order.objects.get(pk=pk))
