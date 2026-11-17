from django.urls import path

from . import tickets, views

urlpatterns = [
    path("dispute-reasons", views.Reasons.as_view()),
    path("orders/<uuid:pk>/disputes", views.OrderDisputes.as_view()),
    path("orders/<uuid:pk>/disputes/open", views.OpenDispute.as_view()),
    path("disputes/<uuid:pk>", views.DisputeDetail.as_view()),
    path("disputes/<uuid:pk>/reply", views.Reply.as_view()),
    path("disputes/<uuid:pk>/appeal", views.Appeal.as_view()),
    path("support/topics", tickets.Topics.as_view()),
    path("support/order-options", tickets.OrderComplaintOptions.as_view()),
    path("support/tickets", tickets.Tickets.as_view()),
    path("support/tickets/<uuid:pk>", tickets.TicketDetail.as_view()),
    path("staff/arbitration", views.ArbitrationQueue.as_view()),
    path("staff/arbitration/<uuid:pk>/claim", views.ArbitrationClaim.as_view()),
    path("staff/disputes", views.StaffQueue.as_view()),
    path("staff/disputes/<uuid:pk>", views.StaffDetail.as_view()),
    path("staff/disputes/<uuid:pk>/<str:action>", views.StaffAction.as_view()),
    path("staff/tickets", tickets.StaffTickets.as_view()),
    path("staff/tickets/<uuid:pk>", tickets.StaffTicketDetail.as_view()),
    path("staff/tickets/<uuid:pk>/<str:action>", tickets.StaffTicketAction.as_view()),
]
