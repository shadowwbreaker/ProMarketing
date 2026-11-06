from django.urls import path

from . import public, views

urlpatterns = [
    path("catalog/home", public.CatalogHome.as_view()),
    path("catalog/accounts", public.CatalogAccounts.as_view()),
    path("catalog/accounts/<uuid:pk>", public.CatalogAccountDetail.as_view()),
    path("catalog/networks", public.CatalogNetworks.as_view()),
    path("catalog/networks/<uuid:pk>", public.CatalogNetworkDetail.as_view()),
    path("sellers/<uuid:pk>", public.SellerPage.as_view()),
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
