from django.urls import path

from . import views

urlpatterns = [
    path("orders/<uuid:pk>/pay", views.StartPayment.as_view()),
    path("payments/webhooks/<str:provider>", views.Webhook.as_view()),
    path("payments/mock/<str:payment_id>/complete", views.MockComplete.as_view()),
    path("me/payouts", views.MyPayouts.as_view()),
    path("me/payouts/<uuid:pk>/withdraw", views.Withdraw.as_view()),
    path("me/payouts/<uuid:pk>/retry", views.RetryPayout.as_view()),
]
