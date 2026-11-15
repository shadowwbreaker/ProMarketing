import csv

from django.db.models import CharField, Count, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Cast, Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView

from chats.inbox import peer_summary
from common.pagination import StandardPagination
from common.permissions import IsActiveUser
from payments.models import Payout, RefundRequest

from .models import Order, OrderItem, OrderStatus
from .state import TERMINAL


def safe_cell(value):
    return f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value


class ReceivedOrders(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        params = request.query_params
        orders = Order.objects.filter(seller=request.user, paid_at__isnull=False)
        if number := params.get("number", "").strip().lstrip("#"):
            orders = orders.annotate(number=Cast("pk", CharField())).filter(number__istartswith=number)
        if buyer := params.get("buyer", "").strip():
            orders = orders.filter(buyer__profile__display_name__icontains=buyer)
        if status := params.get("status"):
            orders = orders.filter(status=status)
        if platform := params.get("platform"):
            orders = orders.filter(items__social_account__platform=platform).distinct()

        first_item = OrderItem.objects.filter(order_id=OuterRef("pk")).order_by("created_at", "pk")
        rows = (orders.select_related("buyer__profile", "network", "current_terms_version")
                .annotate(channel_title=Subquery(first_item.values("social_account__title")[:1]))
                .order_by("-paid_at", "-pk"))
        if params.get("format_csv") == "1":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="yourvideoteam-orders.csv"'
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(["Дата", "Заказ", "Описание", "Покупатель", "Статус", "Сумма", "Валюта"])
            for order in rows.iterator(chunk_size=200):
                writer.writerow([
                    timezone.localtime(order.paid_at).isoformat(), str(order.pk), safe_cell(self.title(order)),
                    safe_cell(order.buyer.profile.display_name), order.get_status_display(),
                    f"{order.total_minor // 100}.{order.total_minor % 100:02d}", order.currency,
                ])
            return response

        summary = orders.aggregate(
            total=Count("pk"), volume=Coalesce(Sum("total_minor"), 0), buyers=Count("buyer", distinct=True),
            completed=Count("pk", filter=Q(status=OrderStatus.COMPLETED)),
            active=Count("pk", filter=~Q(status__in=TERMINAL)),
        )
        order_ids = orders.order_by().values("pk")
        summary["earned_minor"] = Payout.objects.filter(order_item__order_id__in=Subquery(order_ids), status=Payout.Status.PAID).aggregate(
            total=Coalesce(Sum("amount_minor"), 0),
        )["total"]
        refunds = RefundRequest.objects.filter(order_item__order_id__in=Subquery(order_ids), status=RefundRequest.Status.SUCCEEDED)
        summary["refunds"] = refunds.aggregate(orders=Count("order_item__order", distinct=True),
                                                amount_minor=Coalesce(Sum("amount_minor"), 0))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(rows, request)
        response = paginator.get_paginated_response([
            {"id": str(order.pk), "title": self.title(order),
             "brand": order.current_terms_version.brand if order.current_terms_version else "",
             "paid_at": order.paid_at, "buyer": peer_summary(order.buyer), "status": order.status,
             "total_minor": order.total_minor, "currency": order.currency}
            for order in page
        ])
        response.data["summary"] = summary
        return response

    @staticmethod
    def title(order):
        return order.network.title if order.network else order.channel_title or "Размещение рекламы"
