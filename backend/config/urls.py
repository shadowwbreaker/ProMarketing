from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from common.ops import TickView
from common.views import LiveView, MetaView, ReadyView

api_v1 = [
    path("health/live", LiveView.as_view(), name="health-live"),
    path("health/ready", ReadyView.as_view(), name="health-ready"),
    path("meta", MetaView.as_view(), name="meta"),
    path("ops/tick", TickView.as_view(), name="ops-tick"),
    path("", include("accounts.urls")),
    path("", include("social_data.urls")),
    path("", include("catalog.urls")),
    path("", include("orders.urls")),
    path("", include("payments.urls")),
    path("", include("chats.urls")),
    path("", include("files.urls")),
    path("", include("support.urls")),
    path("", include("staff.urls")),
    path("", include("reviews.urls")),
    path("", include("insights.urls")),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/", include(api_v1)),
]
