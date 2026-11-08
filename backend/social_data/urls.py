from django.urls import path

from . import views

urlpatterns = [
    path("social-accounts", views.SocialAccountListCreate.as_view()),
    path("social-accounts/oauth/tiktok/start", views.TikTokOAuthStart.as_view()),
    path("social-accounts/oauth/tiktok/callback", views.TikTokOAuthCallback.as_view()),
    path("social-accounts/<uuid:pk>", views.SocialAccountDetail.as_view()),
    path("social-accounts/<uuid:pk>/ownership/<str:action>", views.SocialAccountOwnership.as_view()),
    path("social-accounts/<uuid:pk>/claim/<str:action>", views.SocialAccountClaim.as_view()),
    path("social-accounts/<uuid:pk>/refresh", views.SocialAccountRefresh.as_view()),
    path("social-accounts/<uuid:pk>/statistics", views.SocialAccountStatsHistory.as_view()),
    path("social-accounts/<uuid:pk>/manual-statistics", views.SocialAccountManualStats.as_view()),
]
