from django.urls import path

from . import views

urlpatterns = [
    path("me/favorites", views.Favorites.as_view()),
    path("me/viewed", views.Viewed.as_view()),
    path("me/recommendations", views.Recommendations.as_view()),
    path("me/analytics", views.Analytics.as_view()),
    path("me/referrals", views.Referrals.as_view()),
    path("catalog/compare", views.Compare.as_view()),
    path("orders/<uuid:pk>/items/<uuid:item_id>/report", views.ItemReport.as_view()),
]
