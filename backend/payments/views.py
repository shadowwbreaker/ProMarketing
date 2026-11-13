from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import DomainError
from common.permissions import IsActiveUser, IsEmailVerified

from . import services
from .models import Payment, Payout
from .providers.registry import get_payment_provider


class StartPayment(APIView):
    permission_classes = [IsEmailVerified]

    def post(self, request, pk):
        payment = services.start_payment(pk, actor=request.user, return_url=f"{settings.FRONTEND_URL}/orders/{pk}")
        return Response({"payment_id": str(payment.pk), "confirmation_url": payment.confirmation_url, "status": payment.status})


@method_decorator(csrf_exempt, name="dispatch")
class Webhook(APIView):
    """Provider → platform. Auth = signature. Duplicates return 200 without reprocessing."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, provider):
        headers = {k: v for k, v in request.headers.items()}
        outcome = services.handle_webhook(provider, headers, request.body)
        return Response({"ok": True, "outcome": outcome})


class MockComplete(APIView):
    """DEV ONLY: emulates the user paying on the mock provider's page, then delivers a signed webhook."""

    permission_classes = [IsActiveUser]

    def post(self, request, payment_id):
        if (settings.ENV == "production" and not settings.BETA_MODE) or settings.PAYMENT_PROVIDER != "mock":
            raise DomainError("Недоступно", code="not_found", status_code=404)
        import uuid as _uuid

        try:
            lookup = {"pk": _uuid.UUID(payment_id)}
        except ValueError:
            lookup = {"provider_payment_id": payment_id}  # id from the mock confirmation_url
        payment = get_object_or_404(Payment, order__buyer=request.user, **lookup)
        status = request.data.get("status", "succeeded")
        if status not in ("succeeded", "cancelled"):
            raise DomainError("Неверный статус", code="bad_status", status_code=400)
        provider = get_payment_provider()
        headers, body = provider.simulate_payment(payment.provider_payment_id, status)
        outcome = services.handle_webhook(provider.code, headers, body)
        return Response({"ok": True, "outcome": outcome})


class PayoutSerializer(serializers.ModelSerializer):
    order = serializers.UUIDField(source="order_item.order_id")
    account = serializers.CharField(source="order_item.social_account.title")

    class Meta:
        model = Payout
        fields = ["id", "status", "amount_minor", "available_at", "paid_at", "order", "account", "created_at"]


class MyPayouts(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        qs = Payout.objects.filter(seller=request.user).select_related("order_item__social_account").order_by("-created_at")
        return Response(PayoutSerializer(qs, many=True).data)


class Withdraw(APIView):
    permission_classes = [IsEmailVerified]

    def post(self, request, pk):
        po = services.withdraw(pk, actor=request.user)
        return Response(PayoutSerializer(Payout.objects.select_related("order_item__social_account").get(pk=po.pk)).data)


class RetryPayout(APIView):
    permission_classes = [IsEmailVerified]

    def post(self, request, pk):
        po = services.retry_failed_payout(pk, actor=request.user)
        return Response(PayoutSerializer(Payout.objects.select_related("order_item__social_account").get(pk=po.pk)).data)
