from django.urls import path

from . import views

urlpatterns = [
    path("staff/dashboard", views.Dashboard.as_view()),
    path("staff/users", views.Users.as_view()),
    path("staff/users/<uuid:pk>", views.UserDetail.as_view()),
    path("staff/users/<uuid:pk>/<str:action>", views.UserSanctionAction.as_view()),
    path("staff/accounts", views.Accounts.as_view()),
    path("staff/accounts/<uuid:pk>", views.AccountDetail.as_view()),
    path("staff/accounts/<uuid:pk>/<str:action>", views.AccountModeration.as_view()),
    path("staff/orders", views.Orders.as_view()),
    path("staff/audit", views.Audit.as_view()),
    path("staff/audit/verify", views.AuditVerify.as_view()),
]
