from django.urls import path

from . import direct, inbox, views

urlpatterns = [
    path("orders/<uuid:pk>/chat", views.Messages.as_view()),
    path("orders/<uuid:pk>/chat/<uuid:msg_id>", views.MessageDetail.as_view()),
    path("messages/orders", inbox.OrderThreads.as_view()),
    path("messages/status", inbox.InboxStatus.as_view()),
    path("direct", direct.DirectThreads.as_view()),
    path("direct/unread-count", direct.DirectUnread.as_view()),
    path("direct/<uuid:user_id>", direct.DirectMessages.as_view()),
]
