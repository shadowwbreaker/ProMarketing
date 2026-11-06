import pytest

from reviews.models import Review
from reviews.services import seller_rating
from tests.test_phase6_orders import as_, item_url, paid_single, to_confirmation


def done(api, market, idx=0):
    oid, iid = paid_single(api, market, offer_idx=idx)
    to_confirmation(api, market, oid, iid)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    return oid, iid


def review(api, user, oid, iid, rating=5, text="Отлично"):
    return as_(api, user).post(item_url(oid, iid, "review"), {"rating": rating, "text": text}, format="json")


@pytest.mark.django_db
def test_review_only_after_completion_once(api, market):
    oid, iid = paid_single(api, market)
    assert review(api, market["buyer"], oid, iid).json()["error"]["code"] == "not_completed"
    to_confirmation(api, market, oid, iid)
    as_(api, market["buyer"]).post(item_url(oid, iid, "confirm"))
    assert review(api, market["seller"], oid, iid).status_code == 404  # only the buyer
    assert review(api, market["buyer"], oid, iid, rating=6).json()["error"]["code"] == "bad_rating"
    r = review(api, market["buyer"], oid, iid, rating=4)
    assert r.status_code == 201
    assert review(api, market["buyer"], oid, iid).json()["error"]["code"] == "review_exists"
    assert seller_rating(market["seller"].pk) == {"rating": 4.0, "reviews_count": 1}
    page = api.get(f"/api/v1/sellers/{market['seller'].pk}").json()
    assert page["rating"] == 4.0 and page["reviews"][0]["text"] == "Отлично"
    assert as_(api, market["buyer"]).get(f"/api/v1/orders/{oid}").json()["items"][0]["review"]["rating"] == 4


@pytest.mark.django_db
def test_rating_recalculation(api, market):
    for idx, rating in [(0, 5), (1, 2), (2, 3)]:
        oid, iid = done(api, market, idx)
        review(api, market["buyer"], oid, iid, rating=rating)
    assert seller_rating(market["seller"].pk) == {"rating": 3.33, "reviews_count": 3}
    card = api.get(f"/api/v1/catalog/accounts/{market['accs'][0].pk}").json()
    assert card["seller"]["rating"] == 3.33


@pytest.mark.django_db
def test_no_review_during_dispute_and_complaint_does_not_lower_rating(api, market, user_factory):
    oid, iid = done(api, market)
    as_(api, market["buyer"]).post(f"/api/v1/orders/{oid}/disputes/open",
                                   {"reason": "removed_early", "description": "Видео удалено на второй день размещения"}, format="json")
    assert review(api, market["buyer"], oid, iid).json()["error"]["code"] == "dispute_active"
    assert seller_rating(market["seller"].pk)["reviews_count"] == 0  # the complaint itself changed nothing


@pytest.mark.django_db
def test_reply_complaint_and_moderation(api, market, user_factory):
    oid, iid = done(api, market)
    rid = review(api, market["buyer"], oid, iid, rating=1, text="Мошенник!!!").json()["id"]
    assert as_(api, market["buyer"]).post(f"/api/v1/reviews/{rid}/reply", {"text": "x"}, format="json").status_code == 403
    s = as_(api, market["seller"])
    assert s.post(f"/api/v1/reviews/{rid}/reply", {"text": "Видео опубликовано по ТЗ"}, format="json").json()["seller_reply"]
    assert s.post(f"/api/v1/reviews/{rid}/reply", {"text": "ещё"}, format="json").json()["error"]["code"] == "reply_exists"
    assert s.post(f"/api/v1/reviews/{rid}/complain", {"reason": "Оскорбление без оснований"}, format="json").status_code == 201
    assert as_(api, user_factory()).post(f"/api/v1/reviews/{rid}/complain", {"reason": "посторонний человек"}, format="json").status_code == 403
    assert Review.objects.get(pk=rid).moderation_status == "published"  # stays until moderator decides
    mod = as_(api, user_factory(roles=("moderator",)))
    assert len(mod.get("/api/v1/staff/reviews", {"complaints": "1"}).json()) == 1
    r = mod.post(f"/api/v1/staff/reviews/{rid}/hide", {"comment": "Оскорбление"}, format="json").json()
    assert r["moderation_status"] == "hidden" and r["complaints"][0]["status"] == "accepted"
    assert seller_rating(market["seller"].pk)["reviews_count"] == 0
    assert as_(api, market["buyer"]).get("/api/v1/staff/reviews").status_code == 403


@pytest.mark.django_db
def test_refund_withdraws_review(api, market):
    from payments.services import refund_item

    oid, iid = done(api, market)
    rid = review(api, market["buyer"], oid, iid).json()["id"]
    refund_item(iid, amount_minor=None, reason="решение по спору", actor=None)
    assert Review.objects.get(pk=rid).moderation_status == "withdrawn"
    assert seller_rating(market["seller"].pk)["reviews_count"] == 0
