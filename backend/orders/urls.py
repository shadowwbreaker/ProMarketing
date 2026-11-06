from django.urls import path

from . import views

I = "orders/<uuid:pk>/items/<uuid:item_id>/"  # noqa: E741

urlpatterns = [
    path("orders", views.OrderCreate.as_view()),
    path("orders/<uuid:pk>", views.OrderDetail.as_view()),
    path("orders/<uuid:pk>/events", views.OrderEvents.as_view()),
    path("orders/<uuid:pk>/terms", views.OrderTermsHistory.as_view()),
    path("orders/<uuid:pk>/terms/propose", views.ProposeTerms.as_view()),
    path("orders/<uuid:pk>/terms/<uuid:proposal_id>/decide", views.DecideTerms.as_view()),
    path("orders/<uuid:pk>/cancel", views.CancelUnpaid.as_view()),
    path("orders/<uuid:pk>/materials-delivered", views.MaterialsDelivered.as_view()),
    path(I + "accept", views.Accept.as_view()),
    path(I + "decline", views.Decline.as_view()),
    path(I + "ready", views.ReadyForPublication.as_view()),
    path(I + "proof", views.SubmitProof.as_view()),
    path(I + "confirm", views.Confirm.as_view()),
    path(I + "rework", views.Rework.as_view()),
    path(I + "cancel", views.CancelItem.as_view()),
    path(I + "check-publication", views.CheckPublication.as_view()),
]
