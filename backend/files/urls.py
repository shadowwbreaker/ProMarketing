from django.urls import path

from . import views

urlpatterns = [path("files", views.Upload.as_view()), path("files/<uuid:pk>", views.Download.as_view())]
