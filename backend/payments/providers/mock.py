"""Mock payment provider for dev/tests (D-008). Refuses to work in production.

Emulates: payments, HMAC-signed webhooks, duplicate deliveries, full/partial/multiple refunds,
payouts, failures and timeouts. Idempotency keys behave like a real provider: same key -> same result.
"""
import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import (
    OperationResult,
    PaymentProvider,
    PaymentSession,
    ProviderCallError,
    ProviderCapabilities,
    VerifiedEvent,
    WebhookSignatureError,
)

FULL_CAPABILITIES = ProviderCapabilities(
    marketplace_split=True, escrow_hold=True, max_hold_days=180, payouts_to_sellers=True,
    multiple_payouts_per_deal=True, partial_refund=True, multiple_refunds=True,
    refund_before_payout=True, pause_payout_on_dispute=True,
)


class MockPaymentProvider(PaymentProvider):
    code = "mock"

    def __init__(self, capabilities: ProviderCapabilities = FULL_CAPABILITIES, secret: str | None = None):
        if getattr(settings, "ENV", "dev") == "production":
            raise ImproperlyConfigured("MockPaymentProvider is forbidden in production")
        self.capabilities = capabilities
        self.secret = (secret or settings.MOCK_PAYMENT_WEBHOOK_SECRET).encode()
        self.payments: dict[str, dict] = {}
        self.refunds: dict[str, dict] = {}
        self.payouts: dict[str, dict] = {}
        self._by_key: dict[str, object] = {}
        self.fail_next: str | None = None  # "refund" | "payout" | "timeout_refund" | "timeout_payout"

    # --- payments ---
    def create_payment(self, *, order_id, amount_minor, currency, idempotency_key, return_url, description=""):
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        pid = f"mock_pay_{uuid.uuid4().hex[:16]}"
        self.payments[pid] = {"amount": amount_minor, "currency": currency, "status": "pending", "refunded": 0, "order_id": order_id}
        session = PaymentSession(provider_payment_id=pid, confirmation_url=f"{return_url}?mock_payment={pid}", status="pending")
        self._by_key[idempotency_key] = session
        return session

    def get_payment_status(self, provider_payment_id):
        return self.payments[provider_payment_id]["status"]

    def simulate_payment(self, provider_payment_id: str, status: str = "succeeded") -> tuple[dict, bytes]:
        """Change payment state and return a signed webhook (headers, body) to deliver."""
        self.payments[provider_payment_id]["status"] = status
        return self.build_webhook(f"payment.{status}", provider_payment_id, {"amount": self.payments[provider_payment_id]["amount"]})

    def build_webhook(self, event_type: str, object_id: str, data: dict | None = None, event_id: str | None = None):
        body = json.dumps({"id": event_id or f"evt_{uuid.uuid4().hex[:16]}", "type": event_type,
                           "object_id": object_id, "data": data or {}}).encode()
        sig = hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        return {"X-Mock-Signature": sig}, body

    def verify_webhook(self, headers, raw_body):
        sig = headers.get("X-Mock-Signature") or headers.get("HTTP_X_MOCK_SIGNATURE") or ""
        expected = hmac.new(self.secret, raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise WebhookSignatureError("invalid signature")
        data = json.loads(raw_body)
        return VerifiedEvent(event_id=data["id"], type=data["type"], object_id=data["object_id"], data=data.get("data", {}))

    # --- refunds ---
    def request_refund(self, *, provider_payment_id, amount_minor, idempotency_key, reason):
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        if self.fail_next == "timeout_refund":
            self.fail_next = None
            raise ProviderCallError("timeout")
        p = self.payments[provider_payment_id]
        if p["status"] != "succeeded":
            raise ValueError("payment not succeeded")
        if amount_minor != p["amount"] - p["refunded"] and not self.capabilities.partial_refund:
            raise ValueError("partial refunds not supported")
        if p["refunded"] + amount_minor > p["amount"]:
            raise ValueError("refund exceeds payment")
        rid = f"mock_ref_{uuid.uuid4().hex[:16]}"
        status = "failed" if self.fail_next == "refund" else "succeeded"
        self.fail_next = None if self.fail_next == "refund" else self.fail_next
        if status == "succeeded":
            p["refunded"] += amount_minor
        self.refunds[rid] = {"payment": provider_payment_id, "amount": amount_minor, "status": status}
        result = OperationResult(provider_id=rid, status=status)
        self._by_key[idempotency_key] = result
        return result

    def get_refund_status(self, provider_refund_id):
        return self.refunds[provider_refund_id]["status"]

    # --- payouts ---
    def request_payout(self, *, seller_ref, amount_minor, idempotency_key, deal_ref=""):
        if not self.capabilities.payouts_to_sellers:
            raise NotImplementedError("payouts not supported")
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        if self.fail_next == "timeout_payout":
            self.fail_next = None
            raise ProviderCallError("timeout")
        oid = f"mock_po_{uuid.uuid4().hex[:16]}"
        status = "failed" if self.fail_next == "payout" else "succeeded"
        self.fail_next = None if self.fail_next == "payout" else self.fail_next
        self.payouts[oid] = {"seller": seller_ref, "amount": amount_minor, "status": status}
        result = OperationResult(provider_id=oid, status=status)
        self._by_key[idempotency_key] = result
        return result

    def get_payout_status(self, provider_payout_id):
        return self.payouts[provider_payout_id]["status"]
