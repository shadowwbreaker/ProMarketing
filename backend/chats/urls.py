from django.urls import path

from . import views

urlpatterns = [
    path("orders/<uuid:pk>/chat", views.Messages.as_view()),
    path("orders/<uuid:pk>/chat/<uuid:msg_id>", views.MessageDetail.as_view()),
]
