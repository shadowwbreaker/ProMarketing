from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.public import network_card, offer_card, sellable_accounts, sellable_networks
from common.exceptions import DomainError
from common.permissions import IsActiveUser
from reviews.services import ratings_for

from . import services
from .models import Favorite


def _cards(accounts):
    ratings = ratings_for({a.owner_id for a in accounts})
    return [offer_card(a, ratings) for a in accounts]


class Favorites(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        acc_ids = Favorite.objects.filter(user=request.user, social_account__isnull=False).values_list("social_account_id", flat=True)
        net_ids = Favorite.objects.filter(user=request.user, network__isnull=False).values_list("network_id", flat=True)
        accs = list(sellable_accounts().filter(pk__in=acc_ids).prefetch_related("offers"))
        nets = list(sellable_networks().filter(pk__in=net_ids))
        ratings = ratings_for({n.owner_id for n in nets})
        return Response({"accounts": _cards(accs), "networks": [network_card(n, ratings) for n in nets]})

    def post(self, request):
        on = services.toggle_favorite(request.user, account_id=request.data.get("account"), network_id=request.data.get("network"))
        return Response({"favorite": on})


class Analytics(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        data = {"buyer": services.buyer_analytics(request.user)}
        if request.user.has_role("seller"):
            data["seller"] = services.seller_analytics(request.user)
        return Response(data)


class ItemReport(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, pk, item_id):
        from orders.models import OrderItem

        item = get_object_or_404(OrderItem.objects.select_related("order"), pk=item_id, order_id=pk)
        if request.user.pk not in (item.order.buyer_id, item.order.seller_id) and not request.user.has_perm_code("staff.view_orders"):
            raise DomainError("Нет доступа", code="forbidden", status_code=404)
        return Response(services.result_report(item))


class Referrals(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        return Response(services.referral_stats(request.user))
