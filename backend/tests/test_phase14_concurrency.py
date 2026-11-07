"""Real concurrency (separate DB connections in threads): double refund, duplicate webhook, double withdraw."""
import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from payments.models import Payment, PaymentWebhookEvent, RefundRequest
from tests.test_phase6_orders import as_, create, item_url, paid_single, to_confirmation


def run_parallel(fn, n=5):
    results, barrier = [], threading.Barrier(n)

    def worker():
        try:
            barrier.wait()
            results.append(("ok", fn()))
        except Exception as e:  # noqa: BLE001
            results.append(("err", type(e).__name__))
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


@pytest.mark.django_db(transaction=True)
def test_parallel_full_refunds_execute_once(api, market, mock_provider):
    from payments.services import refund_item

    oid, iid = paid_single(api, market)
    res = run_parallel(lambda: refund_item(iid, amount_minor=None, reason="race", actor=None).pk)
    assert sum(1 for s, _ in res if s == "ok") == 1
    assert RefundRequest.objects.filter(order_item_id=iid).count() == 1
    p = Payment.objects.get(order_id=oid)
    assert mock_provider.payments[p.provider_payment_id]["refunded"] == 100_000


@pytest.mark.django_db(transaction=True)
def test_parallel_duplicate_webhooks_processed_once(api, market, mock_provider):
    from payments.services import handle_webhook

    oid = create(api, market["buyer"], offer=str(market["offers"][0].pk)).json()["id"]
    pid = api.post(f"/api/v1/orders/{oid}/pay").json()["payment_id"]
    headers, body = mock_provider.simulate_payment(Payment.objects.get(pk=pid).provider_payment_id)
    res = run_parallel(lambda: handle_webhook("mock", headers, body))
    outcomes = sorted(v for s, v in res if s == "ok")
    assert outcomes.count("paid") == 1 and PaymentWebhookEvent.objects.count() == 1
    from payments.models import FinancialLedgerEntry

    assert FinancialLedgerEntry.objects.filter(kind="payment_succeeded").count() == 1


@pytest.mark.django_db(transaction=True)
def test_parallel_withdraw_pays_once(api, market, mock_provider):
    from payments.models import Payout
    from payments.services import release_payouts, withdraw

    oid, iid = paid_single(api, market)
    to_confirmation(api, market, oid, iid)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    release_payouts(timezone.now() + timedelta(hours=49))
    po = Payout.objects.get(order_item_id=iid)
    res = run_parallel(lambda: withdraw(po.pk, actor=market["seller"]).status)
    assert [v for s, v in res if s == "ok"] == ["paid"]
    assert len(mock_provider.payouts) == 1


@pytest.mark.django_db(transaction=True)
def test_parallel_disputes_on_same_item_single_active(api, market):
    from support.models import DisputeItem
    from support.services import open_dispute

    oid, iid = paid_single(api, market)
    as_(api, market["seller"]).post(item_url(oid, iid, "accept"))
    res = run_parallel(lambda: open_dispute(oid, actor=market["buyer"], item_ids=[iid], reason_code="not_published",
                                            description="Видео не опубликовано в срок, продавец молчит").pk, n=4)
    assert sum(1 for s, _ in res if s == "ok") == 1
    assert DisputeItem.objects.filter(order_item_id=iid, is_active=True).count() == 1
