"""Database-backed payment simulator shared by Vercel function instances."""
from django.db import transaction

from payments.models import BetaProviderOperation

from .base import OperationResult, PaymentSession
from .mock import MockPaymentProvider


class BetaPaymentProvider(MockPaymentProvider):
    def create_payment(self, *, order_id, amount_minor, currency, idempotency_key, return_url, description=""):
        payment, _ = BetaProviderOperation.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={"kind": "pay", "amount_minor": amount_minor, "status": "pending"},
        )
        return PaymentSession(
            provider_payment_id=payment.provider_id,
            confirmation_url=f"{return_url}?mock_payment={payment.provider_id}",
            status=payment.status,
        )

    def _get(self, kind, provider_id):
        return BetaProviderOperation.objects.get(kind=kind, pk=provider_id.removeprefix(f"mock_{kind}_"))

    def get_payment_status(self, provider_payment_id):
        return self._get("pay", provider_payment_id).status

    @transaction.atomic
    def simulate_payment(self, provider_payment_id, status="succeeded"):
        payment = BetaProviderOperation.objects.select_for_update().get(
            kind="pay", pk=provider_payment_id.removeprefix("mock_pay_"),
        )
        if payment.status == "pending":
            payment.status = status
            payment.save(update_fields=["status"])
        return self.build_webhook(f"payment.{payment.status}", provider_payment_id, {"amount": payment.amount_minor})

    @transaction.atomic
    def request_refund(self, *, provider_payment_id, amount_minor, idempotency_key, reason):
        payment = BetaProviderOperation.objects.select_for_update().get(
            kind="pay", pk=provider_payment_id.removeprefix("mock_pay_"),
        )
        previous = BetaProviderOperation.objects.filter(idempotency_key=idempotency_key).first()
        if previous:
            return OperationResult(provider_id=previous.provider_id, status=previous.status)
        if payment.status != "succeeded":
            raise ValueError("payment not succeeded")
        if payment.refunded_minor + amount_minor > payment.amount_minor:
            raise ValueError("refund exceeds payment")
        refund = BetaProviderOperation.objects.create(
            kind="ref", idempotency_key=idempotency_key, amount_minor=amount_minor, status="succeeded",
        )
        payment.refunded_minor += amount_minor
        payment.save(update_fields=["refunded_minor"])
        return OperationResult(provider_id=refund.provider_id, status=refund.status)

    def get_refund_status(self, provider_refund_id):
        return self._get("ref", provider_refund_id).status

    def request_payout(self, *, seller_ref, amount_minor, idempotency_key, deal_ref=""):
        payout, _ = BetaProviderOperation.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={"kind": "po", "amount_minor": amount_minor, "status": "succeeded"},
        )
        return OperationResult(provider_id=payout.provider_id, status=payout.status)

    def get_payout_status(self, provider_payout_id):
        return self._get("po", provider_payout_id).status
