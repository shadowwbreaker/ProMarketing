"""User cabinet endpoints (roadmap Phase 2). Every queryset is scoped to request.user — no object IDs from
other users can leak through these views."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from catalog.models import AccountNetwork
from common.permissions import IsActiveUser
from notifications.models import Notification
from orders.models import Order
from reviews.models import Review
from social_data.models import SocialAccount
from support.models import SupportTicket


class OrderBriefSerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "status", "total_minor", "currency", "created_at", "paid_at", "items_count", "buyer", "seller"]


class SocialAccountBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccount
        fields = ["id", "platform", "handle", "title", "status", "is_listed", "created_at"]


class NetworkBriefSerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = AccountNetwork
        fields = ["id", "title", "is_active", "items_count", "created_at"]


class ReviewBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "order_item", "author", "target_user", "rating", "text", "seller_reply", "moderation_status", "created_at"]


class TicketBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["id", "category", "subject", "status", "priority", "order", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "title", "body", "payload", "read_at", "created_at"]


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "action", "subject_type", "subject_id", "created_at"]


class _Mine(generics.ListAPIView):
    permission_classes = [IsActiveUser]


class MyPurchases(_Mine):
    serializer_class = OrderBriefSerializer

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).order_by("-created_at")


class MySales(_Mine):
    serializer_class = OrderBriefSerializer

    def get_queryset(self):
        return Order.objects.filter(seller=self.request.user).exclude(status="DRAFT").order_by("-created_at")


class MyAccounts(_Mine):
    serializer_class = SocialAccountBriefSerializer

    def get_queryset(self):
        return SocialAccount.objects.filter(owner=self.request.user).exclude(status="removed").order_by("-created_at")


class MyNetworks(_Mine):
    serializer_class = NetworkBriefSerializer

    def get_queryset(self):
        return AccountNetwork.objects.filter(owner=self.request.user).order_by("-created_at")


class MyReviews(_Mine):
    serializer_class = ReviewBriefSerializer

    def get_queryset(self):
        u = self.request.user
        kind = self.request.query_params.get("kind", "received")
        qs = Review.objects.filter(author=u) if kind == "written" else Review.objects.filter(target_user=u)
        return qs.order_by("-created_at")


class MyTickets(_Mine):
    serializer_class = TicketBriefSerializer

    def get_queryset(self):
        return SupportTicket.objects.filter(author=self.request.user).order_by("-created_at")


class MyNotifications(_Mine):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get("unread") == "1":
            qs = qs.filter(read_at__isnull=True)
        return qs.order_by("-created_at")


class NotificationRead(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, pk):
        n = get_object_or_404(Notification, pk=pk, user=request.user)  # 404 for other users' notifications
        if n.read_at is None:
            n.read_at = timezone.now()
            n.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(n).data)


class MyActivity(_Mine):
    serializer_class = ActivitySerializer

    def get_queryset(self):
        return AuditLog.objects.filter(actor=self.request.user).order_by("-seq")
