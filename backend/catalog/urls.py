from django.urls import path

from . import views

urlpatterns = [
    path("ad-formats", views.AdFormatsView.as_view()),
    path("social-accounts/<uuid:pk>/manage", views.AccountManageView.as_view()),
    path("social-accounts/<uuid:pk>/listing", views.AccountListingView.as_view()),
    path("social-accounts/<uuid:pk>/offers", views.AccountOffersView.as_view()),
    path("social-accounts/<uuid:pk>/orders", views.AccountOrdersView.as_view()),
    path("offers/<uuid:pk>", views.OfferDetailView.as_view()),
    path("networks", views.NetworkListCreate.as_view()),
    path("networks/<uuid:pk>", views.NetworkDetail.as_view()),
    path("networks/<uuid:pk>/items", views.NetworkItems.as_view()),
    path("networks/<uuid:pk>/items/<uuid:item_id>", views.NetworkItemDelete.as_view()),
]
