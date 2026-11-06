from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from common.views import LiveView, ReadyView

api_v1 = [
    path("health/live", LiveView.as_view(), name="health-live"),
    path("health/ready", ReadyView.as_view(), name="health-ready"),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/", include(api_v1)),
]
