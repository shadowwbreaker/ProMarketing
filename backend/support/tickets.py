from django.db import transaction
from django.db.models import Case, CharField, F, Q, Value, When
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from common.throttles import ScopedRateThrottle
from rest_framework.views import APIView

from audit.services import record
from common.exceptions import DomainError
from common.pagination import StandardPagination
from common.permissions import HasPerm, IsActiveUser
from notifications.services import notify
from orders.models import Order
from orders.numbers import number_filter

from . import services
from .models import ACTIVE_DISPUTE_STATUSES, AdminNote, Dispute, DisputeReason, DisputeStatus, SupportTicket, TicketMessage
from .views import EvidenceIn

S = SupportTicket.Status
TOPICS = {
    "order": "Проблема с заказом",
    "refund": "Возврат средств",
    "payment": "Оплата и возврат",
    "publication": "Публикация рекламы",
    "account": "Аккаунт и вход",
    "technical": "Техническая проблема",
    "general": "Другой вопрос",
}
ORDER_CATEGORIES = ("order", "refund")
GROUPS = {"refund": "Возврат средств", "complaint": "Жалоба на продавца или покупателя", "other": "Прочее"}
TRANSFERRED = "arbitration"


def request_group(category, kind):
    if category == "refund":
        return "refund"
    return "complaint" if kind == "dispute" or category == "order" else "other"


class Topics(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        return Response(TOPICS)


class NewTicket(serializers.Serializer):
    category = serializers.ChoiceField(choices=TOPICS, default="general")
    subject = serializers.CharField(min_length=3, max_length=200, required=False)
    body = serializers.CharField(min_length=10, max_length=10000)
    order_number = serializers.CharField(max_length=37, required=False, allow_blank=True)
    order = serializers.UUIDField(required=False, write_only=True)
    reason = serializers.CharField(max_length=48, required=False)
    items = serializers.ListField(child=serializers.UUIDField(), required=False)
    evidence = EvidenceIn(many=True, required=False, max_length=10)

    def validate(self, data):
        if data["category"] in ORDER_CATEGORIES:
            if not (data.get("order_number") or data.get("order")):
                raise serializers.ValidationError({"order_number": "Укажите номер заказа."})
            if not data.get("reason"):
                raise serializers.ValidationError({"reason": "Выберите причину жалобы."})
        return data


def own_order(user, number):
    match = number_filter(number)
    own = Order.objects.filter(Q(buyer=user) | Q(seller=user))
    rows = list(own.filter(match).order_by("pk")[:2]) if match is not None else []
    if not rows:
        raise DomainError("Заказ с таким номером не найден среди ваших заказов", code="order_not_found", status_code=404)
    if len(rows) > 1:
        raise DomainError("Укажите полный номер заказа", code="ambiguous_order", status_code=400)
    return rows[0]


class OrderComplaintOptions(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request):
        number = serializers.CharField(max_length=37).run_validation(request.query_params.get("number"))
        order = own_order(request.user, number)
        role = "buyer" if order.buyer_id == request.user.pk else "seller"
        reasons = DisputeReason.objects.filter(is_active=True, allowed_for__in=(role, "both")).values("code", "title")
        items = order.items.order_by("pk").values("id", title=F("social_account__title"))
        return Response({"reasons": list(reasons), "items": list(items)})


def message_body(data):
    return serializers.CharField(max_length=10000).run_validation(data.get("body"))


def payload(ticket, *, detail=False, viewer=None):
    out = {
        "id": str(ticket.pk), "kind": "ticket", "subject": ticket.subject, "category": ticket.category,
        "topic": TOPICS.get(ticket.category, ticket.category),
        "status": ticket.status, "status_label": ticket.get_status_display(),
        "created_at": ticket.created_at, "priority": ticket.priority,
        "order": str(ticket.order_id) if ticket.order_id else None,
        "order_number": str(ticket.order_id)[:8] if ticket.order_id else None,
    }
    if ticket.arbitration_id:
        out.update(status=TRANSFERRED, status_label="Передано в арбитраж", arbitration_id=str(ticket.arbitration_id))
        if ticket.arbitration.status not in ACTIVE_DISPUTE_STATUSES:
            out.update(status=S.CLOSED, status_label=S.CLOSED.label)
    if viewer:
        out.update(author=ticket.author.email, assigned_to_me=ticket.assignee_id == viewer.pk,
                   available=ticket.assignee_id is None and ticket.status != S.CLOSED)
    if detail:
        out["messages"] = list(ticket.messages.order_by("created_at", "pk").values(
            "id", "body", "is_staff_reply", "created_at",
        ))
    return out


def request_page(view, request, tickets, disputes, *, staff=False):
    columns = ("pk", "kind", "created_at", "display_status", "order_id", "author_email", "topic_code", "title")
    tickets = tickets.order_by().annotate(
        kind=Value("ticket"), author_email=F("author__email"), topic_code=F("category"), title=F("subject"),
        display_status=Case(
            When(arbitration__status__in=ACTIVE_DISPUTE_STATUSES, then=Value(TRANSFERRED)),
            When(arbitration__isnull=False, then=Value(S.CLOSED)),
            default=F("status"),
        ),
    ).values(*columns)
    disputes = disputes.order_by().annotate(
        kind=Value("dispute"), author_email=F("opened_by__email"),
        topic_code=Case(When(intake_category="refund", then=Value("refund")), default=Value("order"), output_field=CharField()),
        title=F("reason__title"), display_status=F("status"),
    ).values(*columns)

    pager = StandardPagination()
    rows = pager.paginate_queryset(tickets.union(disputes, all=True).order_by("-created_at", "-pk", "kind"), request, view=view)
    results = []
    for row in rows:
        kind, category, status = row["kind"], row["topic_code"], row["display_status"]
        labels = DisputeStatus if kind == "dispute" else S
        order = str(row["order_id"]) if row["order_id"] else None
        results.append({
            "id": str(row["pk"]), "kind": kind, "subject": row["title"], "category": category,
            "topic": TOPICS.get(category, category), "reason": row["title"] if kind == "dispute" else TOPICS.get(category, category),
            "status": status, "status_label": "Передано в арбитраж" if status == TRANSFERRED else labels(status).label,
            "group": request_group(category, kind), "created_at": row["created_at"],
            "order": order, "order_number": order[:8] if order else None,
            **({"author": row["author_email"]} if staff else {}),
        })
    return pager.get_paginated_response(results)


class Tickets(APIView):
    permission_classes = [IsActiveUser]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "ticket"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get(self, request):
        user = request.user
        disputes = Dispute.objects.filter(Q(order__buyer=user) | Q(order__seller=user)).exclude(intake_tickets__author=user)
        return request_page(self, request, SupportTicket.objects.filter(author=user), disputes)

    @transaction.atomic
    def post(self, request):
        form = NewTicket(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        number = data.get("order_number") or str(data.get("order") or "")
        order = own_order(request.user, number) if number else None
        category = data["category"]
        if category in ORDER_CATEGORIES:
            dispute = services.open_dispute(order.pk, actor=request.user, item_ids=data.get("items", []),
                                            reason_code=data["reason"], description=data["body"],
                                            evidence=data.get("evidence"), intake_category=category)
            return Response({"id": str(dispute.pk), "kind": "dispute", "order": str(order.pk)}, status=201)
        ticket = SupportTicket.objects.create(author=request.user, order=order, category=category,
                                              subject=data.get("subject", TOPICS[category]))
        TicketMessage.objects.create(ticket=ticket, author=request.user, body=data["body"])
        return Response(payload(ticket), status=201)


class TicketDetail(APIView):
    permission_classes = [IsActiveUser]

    def get(self, request, pk):
        return Response(payload(get_object_or_404(SupportTicket, pk=pk, author=request.user), detail=True))

    @transaction.atomic
    def post(self, request, pk):
        ticket = get_object_or_404(SupportTicket.objects.select_for_update(), pk=pk, author=request.user)
        if ticket.status == S.CLOSED or ticket.arbitration_id:
            raise DomainError("Переписка по обращению закрыта", code="ticket_closed")
        TicketMessage.objects.create(ticket=ticket, author=request.user, body=message_body(request.data))
        ticket.status = S.IN_PROGRESS if ticket.assignee_id else S.OPEN
        ticket.save(update_fields=["status", "updated_at"])
        return Response(payload(ticket, detail=True))


def independent_tickets(queryset, user):
    return queryset.exclude(author=user).exclude(Q(order__buyer=user) | Q(order__seller=user))


def independent_disputes(queryset, user):
    return queryset.exclude(Q(order__buyer=user) | Q(order__seller=user))


def visible_tickets(user):
    return independent_tickets(SupportTicket.objects.filter(arbitration__isnull=True), user).filter(
        Q(assignee=user) | (Q(assignee__isnull=True) & ~Q(status=S.CLOSED)),
    )


class StaffTickets(APIView):
    permission_classes = [HasPerm("support.work")]

    def get(self, request):
        if request.query_params.get("scope") == "mine":
            tickets = SupportTicket.objects.filter(assignee=request.user)
            disputes = Dispute.objects.filter(assignee=request.user)
        else:
            tickets = SupportTicket.objects.filter(assignee__isnull=True).exclude(status=S.CLOSED)
            disputes = Dispute.objects.filter(assignee__isnull=True, status__in=ACTIVE_DISPUTE_STATUSES,
                                               appeals__isnull=True)
        tickets = independent_tickets(tickets.filter(arbitration__isnull=True), request.user)
        disputes = independent_disputes(disputes.filter(referred_at__isnull=True), request.user)
        group = request.query_params.get("group")
        if group == "refund":
            tickets = tickets.filter(category="refund")
            disputes = disputes.filter(intake_category="refund")
        elif group == "complaint":
            tickets = tickets.filter(category="order")
            disputes = disputes.exclude(intake_category="refund")
        elif group == "other":
            tickets = tickets.exclude(category__in=ORDER_CATEGORIES)
            disputes = disputes.none()
        elif category := request.query_params.get("category"):
            tickets = tickets.filter(category=category)
            if category not in ORDER_CATEGORIES:
                disputes = disputes.none()
            elif category == "refund":
                disputes = disputes.filter(intake_category="refund")
            else:
                disputes = disputes.exclude(intake_category="refund")
        return request_page(self, request, tickets, disputes, staff=True)


def visible_intake_disputes(user):
    return independent_disputes(Dispute.objects.filter(referred_at__isnull=True), user).filter(
        Q(assignee=user) | Q(assignee__isnull=True, status__in=ACTIVE_DISPUTE_STATUSES, appeals__isnull=True),
    )


def complaint_thread(dispute, viewer):
    category = "refund" if dispute.intake_category == "refund" else "order"
    order = str(dispute.order_id)
    active = dispute.status in ACTIVE_DISPUTE_STATUSES and dispute.items.filter(is_active=True).exists()
    return {
        "id": str(dispute.pk), "kind": "dispute", "subject": dispute.reason.title,
        "category": category, "topic": TOPICS[category], "reason": dispute.reason.title,
        "author": dispute.opened_by.email, "created_at": dispute.created_at,
        "status": dispute.status if active else S.CLOSED, "status_label": dispute.get_status_display(),
        "order": order, "order_number": order[:8], "assigned_to_me": dispute.assignee_id == viewer.pk,
        "available": active and dispute.assignee_id is None,
        "messages": [
            {"id": str(dispute.pk), "body": dispute.description, "is_staff_reply": False, "created_at": dispute.created_at},
            *[{"id": str(m.pk), "body": m.body, "is_staff_reply": m.author_id not in
               (dispute.order.buyer_id, dispute.order.seller_id), "created_at": m.created_at}
              for m in dispute.messages.filter(visibility="all").order_by("created_at", "pk")],
        ],
    }


class StaffTicketDetail(APIView):
    permission_classes = [HasPerm("support.work")]

    def get(self, request, pk):
        ticket = visible_tickets(request.user).select_related("author").filter(pk=pk).first()
        if ticket:
            return Response(payload(ticket, detail=True, viewer=request.user))
        dispute = get_object_or_404(visible_intake_disputes(request.user).select_related("reason", "order", "opened_by"), pk=pk)
        return Response(complaint_thread(dispute, request.user))


def request_order(data, order_id):
    if data.get("order") is not None:
        value = serializers.UUIDField().run_validation(data.get("order"))
        if value != order_id:
            raise DomainError("Обращение относится к другому заказу", code="wrong_order", status_code=404)


def refer_ticket(ticket, user):
    if not ticket.order_id:
        raise DomainError("Для арбитража нужен заказ", code="order_required", status_code=400)
    Order.objects.select_for_update().only("pk").get(pk=ticket.order_id)
    candidates = list(Dispute.objects.select_for_update(of=("self",)).filter(
        order_id=ticket.order_id, status__in=ACTIVE_DISPUTE_STATUSES, appeals__isnull=True,
    ).order_by("pk")[:2])
    if len(candidates) > 1:
        raise DomainError("У заказа несколько открытых жалоб. Передайте нужную жалобу из очереди.", code="ambiguous_dispute")
    first_message = ticket.messages.order_by("created_at", "pk").values_list("body", flat=True).first()
    if candidates:
        dispute = candidates[0]
    else:
        description = f"{ticket.subject}\n\n{first_message or ''}"[:10000]
        dispute = services.open_dispute(ticket.order_id, actor=ticket.author, item_ids=[],
                                        reason_code="other", description=description, intake_category="order")
    if not dispute.referred_at:
        if dispute.assignee_id != user.pk:
            services.assign(dispute.pk, actor=user, assignee=user)
        dispute = services.refer_to_arbitration(dispute.pk, actor=user)
    conversation = "\n\n".join(
        f"{'Техническая поддержка' if m.is_staff_reply else 'Пользователь'} — {m.body}"
        for m in ticket.messages.order_by("created_at", "pk")
    )
    AdminNote.objects.create(subject_type="dispute", subject_id=dispute.pk, author=user,
                             body=(f"Передано из обращения «{ticket.subject}»\n\n" + conversation)[:10000])
    ticket.arbitration = dispute
    ticket.save(update_fields=["arbitration", "updated_at"])
    record(action="ticket.referred", subject_type="ticket", subject_id=ticket.pk, actor=user, order_id=ticket.order_id,
           is_staff_action=True, after={"dispute": str(dispute.pk)})
    return dispute


class StaffTicketAction(APIView):
    permission_classes = [HasPerm("support.work")]

    def complaint_action(self, request, pk, action):
        user = request.user
        dispute = get_object_or_404(Dispute, pk=pk, referred_at__isnull=True)
        request_order(request.data, dispute.order_id)
        if action == "close":
            services.close_without_refund(pk, actor=user, comment="Обращение решено поддержкой без возврата средств.")
        elif action == "assign":
            services.assign(pk, actor=user, assignee=user)
        elif action == "refer":
            services.refer_to_arbitration(pk, actor=user)
            return Response({"status": TRANSFERRED})
        elif action == "reply":
            with transaction.atomic():
                dispute = Dispute.objects.select_for_update().get(pk=pk, referred_at__isnull=True)
                if dispute.assignee_id != user.pk or dispute.status not in ACTIVE_DISPUTE_STATUSES:
                    raise DomainError("Сначала возьмите обращение в работу", code="ticket_unassigned", status_code=403)
                services.staff_message(pk, actor=user, body=message_body(request.data), internal=False)
        else:
            raise DomainError("Неизвестное действие", code="bad_action", status_code=404)
        dispute.refresh_from_db()
        return Response(complaint_thread(dispute, user))

    def post(self, request, pk, action):
        if not SupportTicket.objects.filter(pk=pk).exists():
            return self.complaint_action(request, pk, action)
        return self.ticket_action(request, pk, action)

    @transaction.atomic
    def ticket_action(self, request, pk, action):
        user = request.user
        ticket = get_object_or_404(SupportTicket.objects.select_for_update(), pk=pk, arbitration__isnull=True)
        request_order(request.data, ticket.order_id)
        if ticket.author_id == user.pk or (ticket.order_id and user.pk in (ticket.order.buyer_id, ticket.order.seller_id)):
            raise DomainError("Нельзя рассматривать собственное обращение", code="conflict_of_interest", status_code=403)
        if ticket.assignee_id not in (None, user.pk):
            raise DomainError("Обращение уже у другого сотрудника", code="ticket_taken", status_code=409)
        if ticket.status == S.CLOSED:
            raise DomainError("Обращение закрыто", code="ticket_closed")
        before = {"status": ticket.status, "assignee": str(ticket.assignee_id or "")}
        if action == "assign":
            if ticket.assignee_id == user.pk:
                return Response(payload(ticket, detail=True, viewer=user))
            ticket.assignee = user
            ticket.status = S.IN_PROGRESS
        else:
            if ticket.assignee_id != user.pk:
                raise DomainError("Сначала возьмите обращение в работу", code="ticket_unassigned", status_code=403)
            if action == "refer":
                refer_ticket(ticket, user)
                return Response({"status": TRANSFERRED})
            if action == "reply":
                TicketMessage.objects.create(ticket=ticket, author=user, is_staff_reply=True, body=message_body(request.data))
                ticket.status = S.WAITING_USER
                notify(ticket.author, "ticket.reply", "Ответ поддержки", ticket.subject, ticket=ticket.pk)
            elif action == "close":
                ticket.status = S.CLOSED
            elif action == "priority":
                ticket.priority = serializers.ChoiceField(choices=SupportTicket.Priority.choices).run_validation(
                    request.data.get("priority"),
                )
            else:
                raise DomainError("Неизвестное действие", code="bad_action", status_code=404)
        ticket.save()
        record(action=f"ticket.{action}", subject_type="ticket", subject_id=ticket.pk, actor=user,
               is_staff_action=True, order_id=ticket.order_id, before=before,
               after={"status": ticket.status, "assignee": str(ticket.assignee_id)})
        return Response(payload(ticket, detail=True, viewer=user))
