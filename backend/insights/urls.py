from django.urls import path

from . import views

urlpatterns = [
    path("me/favorites", views.Favorites.as_view()),
    path("me/analytics", views.Analytics.as_view()),
    path("me/referrals", views.Referrals.as_view()),
    path("orders/<uuid:pk>/items/<uuid:item_id>/report", views.ItemReport.as_view()),
]
