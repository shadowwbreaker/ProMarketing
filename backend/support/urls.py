from django.urls import path

from . import views

urlpatterns = [
    path("dispute-reasons", views.Reasons.as_view()),
    path("orders/<uuid:pk>/disputes", views.OrderDisputes.as_view()),
    path("orders/<uuid:pk>/disputes/open", views.OpenDispute.as_view()),
    path("disputes/<uuid:pk>", views.DisputeDetail.as_view()),
    path("disputes/<uuid:pk>/reply", views.Reply.as_view()),
    path("disputes/<uuid:pk>/appeal", views.Appeal.as_view()),
    path("support/tickets", views.Tickets.as_view()),
    path("support/tickets/<uuid:pk>", views.TicketDetail.as_view()),
    path("staff/disputes", views.StaffQueue.as_view()),
    path("staff/disputes/<uuid:pk>", views.StaffDetail.as_view()),
    path("staff/disputes/<uuid:pk>/<str:action>", views.StaffAction.as_view()),
    path("staff/tickets", views.StaffTickets.as_view()),
    path("staff/tickets/<uuid:pk>/<str:action>", views.StaffTicketAction.as_view()),
]
