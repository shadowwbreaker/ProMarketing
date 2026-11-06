"""Payment Provider Adapter (roadmap 7.2). The platform never stores or moves money itself."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderCapabilities:
    marketplace_split: bool = False
    escrow_hold: bool = False
    max_hold_days: int = 0
    payouts_to_sellers: bool = False
    multiple_payouts_per_deal: bool = False
    partial_refund: bool = False
    multiple_refunds: bool = False
    refund_before_payout: bool = False
    pause_payout_on_dispute: bool = False

    def supports_d014(self) -> tuple[bool, list[str]]:
        """Check requirements of the accepted payout model D-014."""
        missing = [name for name in ("escrow_hold", "payouts_to_sellers", "refund_before_payout") if not getattr(self, name)]
        if self.max_hold_days < 3:
            missing.append("max_hold_days>=3")
        return not missing, missing


@dataclass(frozen=True)
class PaymentSession:
    provider_payment_id: str
    confirmation_url: str
    status: str


@dataclass(frozen=True)
class OperationResult:
    provider_id: str
    status: str  # pending | succeeded | failed | cancelled


@dataclass(frozen=True)
class VerifiedEvent:
    event_id: str
    type: str  # payment.succeeded | payment.cancelled | refund.succeeded | refund.failed | payout.succeeded | payout.failed
    object_id: str
    data: dict = field(default_factory=dict)


class WebhookSignatureError(Exception):
    pass


class ProviderCallError(Exception):
    """Outcome unknown (timeout / 5xx). Operation must go to reconciliation, never be blindly retried."""


class PaymentProvider(ABC):
    code: str
    capabilities: ProviderCapabilities

    @abstractmethod
    def create_payment(self, *, order_id: str, amount_minor: int, currency: str, idempotency_key: str,
                       return_url: str, description: str = "") -> PaymentSession: ...

    @abstractmethod
    def get_payment_status(self, provider_payment_id: str) -> str: ...

    @abstractmethod
    def verify_webhook(self, headers: dict, raw_body: bytes) -> VerifiedEvent: ...

    @abstractmethod
    def request_refund(self, *, provider_payment_id: str, amount_minor: int, idempotency_key: str, reason: str) -> OperationResult: ...

    @abstractmethod
    def get_refund_status(self, provider_refund_id: str) -> str: ...

    def request_payout(self, *, seller_ref: str, amount_minor: int, idempotency_key: str, deal_ref: str = "") -> OperationResult:
        raise NotImplementedError("Provider does not support payouts")

    def get_payout_status(self, provider_payout_id: str) -> str:
        raise NotImplementedError("Provider does not support payouts")
