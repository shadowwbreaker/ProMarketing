from django.urls import path

from . import views

urlpatterns = [
    path("orders/<uuid:pk>/items/<uuid:item_id>/review", views.CreateReview.as_view()),
    path("reviews/<uuid:pk>/reply", views.Reply.as_view()),
    path("reviews/<uuid:pk>/complain", views.Complain.as_view()),
    path("staff/reviews", views.StaffReviews.as_view()),
    path("staff/reviews/<uuid:pk>/<str:action>", views.StaffModerate.as_view()),
]
